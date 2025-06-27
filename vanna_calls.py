import streamlit as st

#Added Packages
from vn_qsBase_session import VN_QsBase
from dotenv import load_dotenv
from qdrant_client import QdrantClient

#import shelve
import toml

#Added for setup_vanna()
load_dotenv('.env')

def get_qdrantClient():
    client = QdrantClient(
        url=st.secrets.get('QDRANT_URL'),
        api_key=st.secrets.get('QDRANT_API_KEY')
    )
    return client

def masked_n_results(n_results:int) -> int:
    if n_results == 0: return 11
    else: return n_results

def get_config():
    config ={
        "client":get_qdrantClient(),
        "fastembed_model":'BAAI/bge-base-en-v1.5',
        "n_results": masked_n_results(0),
        "sql_collection_name" : 'zero_sql',
        "ddl_collection_name" : 'experiment_ddl',
        "api_key": st.secrets.get('OpenAI_API_KEY_DEV'),
        "model": 'gpt-4o-mini'
        }
    return config

#VannaStreamlit
@st.cache_resource(ttl=3600)
def setup_vanna():
    vn = VN_QsBase(config=get_config())
    vn.connect_to_sqlite(st.secrets.get('dbLoc') + '/Chinook/Chinook.sqlite')
    return vn

#@st.cache_data(show_spinner="Generating sample questions ...")
def generate_questions_cached():
    vn = setup_vanna()
    try:
        questions = vn.generate_questions()
    except:
        questions = []
    return questions

@st.cache_data(show_spinner="Interpretating question ...")
def generate_interpretation_cached(question: str):
    vn = setup_vanna()
    try: 
        plan, alternatives = vn.get_interpretation(question)
    except:
        plan, alternatives = None, None
    
    return plan, alternatives

@st.cache_data(show_spinner="Generating SQL query ...")
def generate_sql_cached(question: str, plan: str):
    vn = setup_vanna()
    sql, message = vn.generate_and_correct_sql(question, plan=plan, db_id='Chinook')
    if message == "Not a text-to-sql-question":
        try:
            error_response = vn.generate_error_response(question,message)
            vn._session.add_summaryToLastTurn(error_response)
        except:
            error_response = None
        return error_response
    else:
        db_path= st.secrets.get('dbLoc') + '/Chinook/Chinook.sqlite'
        executable, revised_sql, error = vn.check_sql_for_release(sql, db_path)
        if executable:
            vn._session.add_sqlToLastTurn(vn.extract_sql(sql))
            return revised_sql
        else:
            try:
                error_response = vn.generate_error_response(question,error)
                vn._session.add_summaryToLastTurn(error_response)
            except:
                error_response = None
            return error_response

@st.cache_data(show_spinner="Checking for valid SQL ...")
def is_sql_valid_cached(sql: str):
    vn = setup_vanna()
    return vn.is_sql_valid(sql=sql)

@st.cache_data(show_spinner="Running SQL query ...")
def run_sql_cached(sql: str):
    vn = setup_vanna()
    try:
        df = vn.run_sql(sql=sql)
    except:
        df = None
    return df

@st.cache_data(show_spinner="Checking if we should generate a chart ...")
def should_generate_chart_cached(question, sql, df):
    vn = setup_vanna()
    return vn.should_generate_chart(df=df)

@st.cache_data(show_spinner="Generating Plotly code ...")
def generate_plotly_code_cached(question, sql, df):
    vn = setup_vanna()
    try:
        code = vn.generate_plotly_code(question=question, sql=sql, df=df)
    except:
        code = ''
    return code

@st.cache_data(show_spinner="Running Plotly code ...")
def generate_plot_cached(code, df):
    vn = setup_vanna()
    try:
        fig = vn.get_plotly_figure(plotly_code=code, df=df)
    except:
        fig = None
    return fig

@st.cache_data(show_spinner="Generating followup questions ...")
def generate_followup_cached(question, sql, df):
    vn = setup_vanna()
    return vn.generate_followup_questions(question=question, sql=sql, df=df)

st.cache_data(show_spinner="Generate Explanation")
def generate_interpretation_respond_cached(question, plan):
    vn = setup_vanna()
    try:
        interpretation = vn.genenerate_interpretation_respond(question, plan)
    except:
        interpretation = None
    return interpretation

@st.cache_data(show_spinner="Generating summary ...")
def generate_summary_cached(question, df, alternatives):
    vn = setup_vanna()
    try:
        summary = vn.generate_summary(question, df, alternatives=alternatives)
        vn._session.add_summaryToLastTurn(summary)
    except:
        summary = None
    return summary

#Added for multi-turn-functionanlity
def setUp_newVS():
    vn = setup_vanna()
    vn.setUp_newSession()

def add_turn_to_history(question:str):
    vn = setup_vanna()
    vn._session.add_turnToHistory({'question':question,'query': None, 'summary': None})

# Save chat history to shelve file
#def save_chat_history(messages, sessionName="./history/chat_history"):
    #with shelve.open(sessionName) as db:
        #db["messages"] = messages

def read_file(file):
    f = open(file, 'r', encoding='utf-8')
    return f.read()

st.cache_data(show_spinner="Loading tables")
def get_tableString(db_name):
    vn = setup_vanna()
    vn.connect_to_sqlite(st.secrets.get("dbLoc") + '/' + db_name + '/' + db_name + '.sqlite')
    tbl_df = vn.run_sql("SELECT tbl_name FROM sqlite_master WHERE sql is not null and type = 'table' and tbl_name not like '%sqlite%' ")
    tbl_list = tbl_df['tbl_name'].to_list()
    return str(tbl_list).replace('[','(').replace(']',')')

def override_current_tbl(tbl_name):
    data = get_runtimeParams()
    data['current_tbl'] = tbl_name
    f = open('./.streamlit/runtimeParams.toml','w')
    toml.dump(data, f)
    f.close()
    #st.cache_resource.clear()
    print('current_tbl in runtimeParams has been overridden to ' + tbl_name)

def get_tbl_df(tbl_name: str, db_name: str):
    vn = setup_vanna()
    vn.connect_to_sqlite(st.secrets.get("dbLoc") + '/' + db_name + '/' + db_name + '.sqlite')
    tbl_df = vn.run_sql('SELECT * FROM ' + tbl_name + ' LIMIT 10')
    return tbl_df

def setUp_newTable(tbl_name: str):
    current_tbl = get_runtimeParams()['current_tbl']
    if tbl_name == current_tbl:
        return 'You are already connected to ' + tbl_name
    else:
        override_current_tbl(tbl_name)
        st.cache_data.clear()
        return 'Connection to *' + tbl_name + '* was established'

def get_runtimeParams():
    data = toml.load('./.streamlit/runtimeParams.toml')
    return data

def get_last_df(messages):
    last_df = next((item["content"] for item in reversed(messages) if item.get("type") == "dataframe"), None)
    return last_df

def get_last_df_list(messages):
    df = get_last_df(messages)
    if df is not None:
        return list(df)
    else:
        return []
    
def get_last_num_column_string(messages):
    vn = setup_vanna()
    df = get_last_df(messages)
    if df is not None and vn.should_generate_chart(df):
        num_columns = list(df.select_dtypes(include=['number']))
        non_id_columns = [col for col in num_columns if not col.lower().endswith("id")]
        return str(non_id_columns).replace('[','(').replace(']',')')
    else:
        return '()'
    
def generate_plotly_code_on_demand(df, message):
    vn = setup_vanna()
    try:
        code = vn.generate_plotly_code_on_demand(df=df, message=message)
    except:
        code = None
    return code
    
def get_last_sql(messages):
    last_sql = next((item["content"] for item in reversed(messages) if item.get("type") == "sql"), None)
    return last_sql

def get_related_question(sql, messages):
    for i in range(len(messages) - 1, -1, -1):  
        content = messages[i].get("content")
        
        if isinstance(content, str) and content.strip() == sql.strip():
            if i > 0:
                prev_content = messages[i - 1].get("content")
                return str(prev_content).strip() if prev_content is not None else None
            else:
                return None  
    return None  

st.cache_data(show_spinner="Generate Explanation")
def generate_sql_explanation_on_demand(sql, related_question):
    vn = setup_vanna()
    try:
        explanation = vn.generate_sql_explanation_on_demand(sql, related_question)
    except:
        explanation = None
    return explanation