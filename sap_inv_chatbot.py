## This is a chatbot appliction built using streamlit which can peform the following function :
## • Answer general questions ( as you would with Google search)
## • Perform the following SAP Activities
##     - Query Material Inventory for a given Material and Plant
##     - Show all Material Movements for a given Material and Plant
##     - Trigger the creation of a Purchase order for a given Material, Plant, Qty & UoM
##     - More to follow ……..
##
## Author : Pranav Chaudhari ( pranavc@google.com)


## The following python packages need to be installed prior to running this application:
##  !pip install streamlit --quiet --user
##  !pip install google-cloud-aiplatform --quiet --user
## Assuming the rest of the packages used here are available as a part of you standard Python installation

## Also set up GCP Application Default Credentials running the following command from the command line (Assuming you have Google Cloud SDK installed on your machine)
## gcloud auth application-default login
## These credentials are used to Autheticate the user to enable them to instantiate Vertex AI chat-bison@001 model.


import streamlit as st
import numpy as np
import subprocess
import json
import pandas as pd
import re
import requests
import vertexai
from vertexai.preview.language_models import ChatModel, InputOutputTextPair

# Set up the chatbot Title and Sidebar with Instructions
st.title('💬 SAP Material Inventory Chatbot')

with st.sidebar:
    st.title("Instructions ")
    st.markdown("* You can ask any generic question about anything under the sun ")
    st.markdown("* You can Query for material inventory quantity by providing material number and plant")
    st.markdown("* Ask for Material Movement Information by providing material number and plant")
    st.markdown("* Create a Purchase Order by providing material number, plant, Quantity and UoM")

# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "How can I assist you with Material Inventory related questions?"}]


# Instantiate VertexAI / chat-bison@001 model with context and Example Inputs/Outputs
vertexai.init(project="YOUR GCP PROJECT", location="us-central1")    # Update with your User and Project
chat_model = ChatModel.from_pretrained("chat-bison@001")
parameters = {
    "temperature": 0.2,
    "max_output_tokens": 256,
    "top_p": 0.8,
    "top_k": 40
}
chat = chat_model.start_chat(
    context="""You are a helpful corporate chatbot with access to your company\'s SAP system. If I ask you a question about material inventory information, you identify a function name with parameters from the text the results in json format.  provide concise answers, no explanation. If the question is about anything other the material or inventory provide regular detailed answer.""",
    examples=[
        InputOutputTextPair(
            input_text="""What is the current stock level of EWMS4-01 in plant 1710 ?""",
            output_text="""{\\\"function\\\":\\\"ZPC_MAT_INV_SRV/inv_detSet\\\",\\\"parameters\\\":{\\\"plant\\\":\\\"1710\\\",\\\"material\\\":\\\"EWMS4-01\\\"}}"""
        ),
        InputOutputTextPair(
            input_text="""show me all material movements EWMS4-01 in plant 1710 ?""",
            output_text="""{\"function\":\"ZPC_MAT_MVMT_DET_SRV/goods_mvmtSet\",\"parameters\":\"(Material eq \'EWMS4-01' and Plant eq \'1710\')\"}"""
        ),
        InputOutputTextPair(
            input_text="""show me all goods movement for EWMS4-01 in 1710 """,
            output_text="""{\"function\":\"ZPC_MAT_MVMT_DET_SRV/goods_mvmtSet\",\"parameters\":\"(Material eq \'EWMS4-01' and Plant eq \'1710\')\"}"""
        ),
        InputOutputTextPair(
            input_text="""Wcreate a purchase order for EWMS4-10 in plant 1710 for 10 PC""",
            output_text="""{\\\"function\\\":\\\"ZPC_CREATE_PO_SRV/PoDataSet\\\",\\\"parameters\\\":{\\\"Material\\\":\\\"EWMS4-10\\\",\\\"Plant\\\":\\\"1710\\\",\\\"Quantity\\\":\\\"10\\\",\\\"Unit\\\":\\\"PC\\\"}}"""
        ),     
        InputOutputTextPair(
            input_text="""What is the capital of France""",
            output_text="""The capital of france is Paris"""
        )
    ]
)


# Fetch the external IP address of the SAP system and setup the service URL
ip_addr_cmd = "gcloud compute instances describe https://www.googleapis.com/compute/v1/projects/psosap-demo-343019/zones/us-central1-b/instances/caltdc-265624575-s0020009469-sap-s-4hana-2022-fps01---sap-hana --project=psosap-demo | grep natIP"
ip_addr = subprocess.check_output(ip_addr_cmd, shell=True)
ip_addr = re.findall('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', str(ip_addr))[0]
SERVICE_URL_BASE = f"http://{ip_addr}:50000/sap/opu/odata/SAP/"  # {mod_resp['function']}({param})?$format=json"


# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "How can I assist you with Material Inventory related questions?"}]

# Display or clear chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])


def clear_chat_history():
    st.session_state.messages = [{"role": "assistant", "content": "How can I assist you with Material Inventory related questions?"}]
st.sidebar.button('Clear Chat History', on_click=clear_chat_history)

#def generate_llm_response(prompt_input):
def generate_vertexai_response(prompt_input):
    output = chat.send_message(prompt_input, **parameters)
    return output


# Prepare the model output to generate SAP oData URL and fetch inventory data from SAP
def fetch_inventory_data(mod_resp):
     param_dict = mod_resp["parameters"]
     key, value = list (param_dict.items())[0]
     param=f"{key}=\'{value}\'"
     key, value = list(param_dict.items())[1]
     param= param + ',' + f"{key}=\'{value}\'"

     SERVICE_URL = SERVICE_URL_BASE + f"{mod_resp['function']}({param})?$format=json"

     response = requests.get(SERVICE_URL,auth = ('SAP USER', 'PASSWORD'), headers = {"Prefer": "odata.maxpagesize=500","Prefer": "odata.track-changes"})
     if response.status_code == 200:
        output_json = response.json()['d']
        if output_json['message'] == "":
           output = f"Material : {output_json['material']}\nDescription : {output_json['description']}\nPlant : {output_json['plant']}\nUnit of Measure : {output_json['UoM']}\nUnrestricted Stock : {float(output_json['unres_stock'])}"
        else:
           output = f"{output_json['message']}" 
     return output

# Prepare the model output to generate SAP oData URL and fetch Material Movements data from SAP
def fetch_material_movement(mod_resp):

     param= mod_resp['parameters'].replace(' ','%20')

     SERVICE_URL = SERVICE_URL_BASE + f"{mod_resp['function']}?$filter={param}&$format=json" #({param})?$format=json"
     response = requests.get(SERVICE_URL,auth = ('SAP USER', 'PASSWORD'), headers = {"Prefer": "odata.maxpagesize=500","Prefer": "odata.track-changes"})
     if response.status_code == 200:
        output = response.json()['d']['results']
     else: 
        output = f"Invalid Material or Plant... Please check and try again"
     return response.status_code, output

# Prepare the model output to generate SAP oData URL and create Purchase Order in SAP
def create_purchase_order(mod_resp):
     param_dict = mod_resp["parameters"]
     key, value = list (param_dict.items())[0]
     param=f"{key}=\'{value}\'"
     key, value = list(param_dict.items())[1]
     param= param + ',' + f"{key}=\'{value}\'"
     key, value = list(param_dict.items())[2]
     param= param + ',' + f"{key}={value}"
     key, value = list(param_dict.items())[3]
     param= param + ',' + f"{key}=\'{value}\'"     

     SERVICE_URL = SERVICE_URL_BASE + f"{mod_resp['function']}({param})?$format=json"

     response = requests.get(SERVICE_URL,auth = ('SAP USER', 'PASSWORD'), headers = {"Prefer": "odata.maxpagesize=500","Prefer": "odata.track-changes"})
     if response.status_code == 200:
        output = response.json()['d']['message']
     else:
        output=response

     return output

# User-provided prompt
if prompt := st.chat_input("Please provide SAP Material and Plant numbers in your enquiry"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)


# Generate a new response if last message is not from assistant
if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = generate_vertexai_response(prompt)

            if "ZPC_MAT_INV_SRV" in response.text: 
               inv_data = fetch_inventory_data(json.loads(response.text.replace('\\', '')))
               st.write(inv_data)
               message = {"role": "assistant", "content": inv_data}
            
            elif "ZPC_MAT_MVMT_DET_SRV" in response.text:
               status, mvmt_data = fetch_material_movement(json.loads(response.text.replace('\\', '')))
               
               if status == 200:
                  mvmt_data = json.dumps(mvmt_data)
                  df = pd.read_json(mvmt_data)
                  df['MatDoc'] = df['MatDoc'].astype(str)
                  df['DocYear'] = df['DocYear'].astype(str)
                  df['MatdocItm'] = df['MatdocItm'].astype(str)
                  df['Plant'] = df['Plant'].astype(str)
                  df.drop(columns=['__metadata'], axis=1, inplace=True)
                  st.dataframe(df)
                  message = {"role": "assistant", "content": df}
               else:
                  st.write(mvmt_data)
            
            elif "ZPC_CREATE_PO_SRV" in response.text:
                po_data = create_purchase_order(json.loads(response.text.replace('\\', '')))
                st.write(po_data)
                message = {"role": "assistant", "content": po_data}
            
            else:
               st.write(response.text)
               message = {"role": "assistant", "content": response.text}
    
    st.session_state.messages.append(message)        
