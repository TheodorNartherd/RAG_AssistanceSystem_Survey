import time
import streamlit as st
import vanna_calls as vc
import streamlit_mermaid as stmd
from datetime import datetime

st.set_page_config(layout="wide")

st.title("Assistance-System")

greetings = """
Hi there, and welcome!\n
I'm your **Assistance‑System**. I support **multi‑turn interactions** and go beyond text‑to‑SQL translation with **suggestions**, **database views**, and **auto‑generated diagrams** based on your data.\n
Feel free to **test out the functions** on the **left sidebar**—you can **expand or collapse** it as needed.
"""

def greet_user():
    greet_dict =  {"role": "assistant", "content": greetings, "type": "text"}
    st.session_state.messages.append(greet_dict)
    return [greet_dict]

def app_reload():
    st.session_state.explanation_open = False
    st.session_state.suggestedQuestionList = False
    st.rerun()

def set_question(question):
    st.session_state.messages.append({"role": "user", "content": question, "type": "text"})
    st.session_state.suggestedQuestionList = False
    generate_response(question)

def generate_response(prompt, prePrint=False):
    with st.chat_message("assistant"):
        vc.add_turn_to_history(prompt)
        plan, alternatives = vc.generate_interpretation_cached(prompt)
        if plan:
            if st.session_state.get("show_interpretation"):
                interpretation_resp = vc.generate_interpretation_respond_cached(prompt, plan)
                if prePrint:
                    st.write(interpretation_resp)
                st.session_state.messages.append({"role": "assistant", "content": interpretation_resp, "type": "text"})

        sql = vc.generate_sql_cached(prompt, plan)
        if sql:
            
            if vc.is_sql_valid_cached(sql):
                if st.session_state.get("show_sql"):
                    if prePrint:
                        st.code(sql, language=sql, line_numbers=True, wrap_lines=True)
                    st.session_state.messages.append({"role": "assistant", "content": sql, "type": "sql"})

            else:
                if prePrint:
                    st.error(sql)
                st.session_state.messages.append({"role": "assistant", "content": sql, "type": "error"})
                st.stop()
            
            df = vc.run_sql_cached(sql)

            if df is not None:
                st.session_state["df"] = df

            if st.session_state.get("df") is not None:
                if st.session_state.get("show_table"):
                    df = st.session_state.get("df")
                    if prePrint:
                        st.dataframe(df)
                    st.session_state.messages.append({"role": "assistant", "content": df, "type": "dataframe"})

                if vc.should_generate_chart_cached(prompt,sql,df):
                    code = vc.generate_plotly_code_cached(prompt, sql, df)
                    ###if st.session_state.get("show_plotly_code"):
                        ###if(prePrint):
                            ###st.code(code, language="python", line_numbers=True, wrap_lines=True)
                        ###st.session_state.messages.append({"role": "assistant", "content": code, "type": "python"})

                    if code is not None and code != "":
                        if st.session_state.get("show_chart"):
                            fig = vc.generate_plot_cached(code, df)
                            if fig is not None:
                                if prePrint:
                                    st.plotly_chart(fig, key=id(fig))
                                st.session_state.messages.append({"role": "assistant", "content": fig, "type": "figure"})
                            else: st.error("I couldn't generate a a chart")

                if st.session_state.get("show_summary"):
                    summary = vc.generate_summary_cached(prompt,df,alternatives)

                    if summary is not None:
                        if prePrint:
                            st.write(summary)
                        st.session_state.messages.append({"role": "assistant", "content": summary, "type": "text"})

                #if st.session_state.get("show_followup"):
                    #followup_questions = vc.generate_followup_cached(prompt, sql, df)
                    #st.session_state["df"] = None

                    #if len(followup_questions) > 0:
                        #st.text(
                            #"Here are some possible follow-up questions"
                        #)
                        # Print the first 5 follow-up questions
                        #for question in followup_questions[:5]:
                            #st.button(question, on_click=set_question, args=(question,))

        else:
            errorMessage = "I wasn't able to generate SQL for that question"
            if prePrint:
                st.error(errorMessage)
            st.session_state.messages.append({"role": "assistant", "content": errorMessage, "type": "error"})
    if prePrint:
        app_reload()

#@st.dialog("Save this session")
#def save_session():
    #sessionName = st.text_input("Something", placeholder="name the session", label_visibility="collapsed")
    #if st.button("Save"):
        #vc.save_chat_history(st.session_state.messages, "./history/saved_history/" + datetime.today().strftime("%Y-%m-%d") + '_' + sessionName)
        #st.write('Session saved successfully')
        #time.sleep(1)
        #st.rerun()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.suggestedQuestionList = False
    st.session_state.last_sql = ''
    st.session_state.last_explanation = ''
    st.session_state.explanation_open = False
    greet_user()

with st.sidebar:
    st.title("Tools & Features")

    db_mono = vc.get_runtimeParams()['db_mono']
    current_tbl = vc.get_runtimeParams()['current_tbl']
    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button("New Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.suggestedQuestionList = False
            st.session_state.explanation_open = False
            vc.setUp_newVS()
            st.cache_data.clear()
            greet_user()
            #save_chat_history([])  
    with col2:
        if st.button("Question Suggestion", use_container_width=True):
            #st.session_state["my_question"] = None
            st.session_state.explanation_open = False

            if(st.session_state["suggestedQuestionList"]):
                questions = []
                st.session_state.suggestedQuestionList = False

            else:
                questions = vc.generate_questions_cached()
                st.session_state.suggestedQuestionList = True
                for i, question in enumerate(questions):
                    time.sleep(0.05)
                    button = st.button(
                        question,
                        on_click=set_question,
                        args=(question,),
                    )
        

    with st.expander("Database Structure"):
            
        st.toggle("Dynamic", value=True, key="dynamic_er-diagram")
        direction = st.radio(
            "Set rendering direction:",
            ["Left to Right", "Top to Bottom"],
            horizontal=True,
            disabled= not st.session_state.get("dynamic_er-diagram"),
            label_visibility='collapsed'
        )

        if st.session_state.get("dynamic_er-diagram"):
            if direction == 'Left to Right': direct = '_LR'
            else: direct = ''

            code = vc.read_file('./ER-Diagram/erd_from_'+ db_mono + direct + '_sqlite.md')
            stmd.st_mermaid(eval(code))
        else:
            st.image('./ER-Diagram/erd_from_'+ db_mono +'_sqlite.png')
             

    with st.expander('Table Preview'):
        with st.form('db',clear_on_submit=True):
            selectbox_val = st.selectbox(
                "Explore your tables",
                eval(vc.get_tableString(db_mono)),
                index=None,
                placeholder="Select...",
                )
            submitted = st.form_submit_button("Submit")
            if submitted:
                if(selectbox_val):
                    st.write("You selected:", '*' + selectbox_val + '*')
                    message = vc.setUp_newTable(selectbox_val)
                    st.write(message)
                else:
                    st.write("Please choose a table first.")
                time.sleep(1)
                app_reload()

        tbl_df = vc.get_tbl_df(current_tbl,db_mono)
        st.write('Preview of the table: ' + '**'+ current_tbl + '**')
        st.dataframe(tbl_df)        


    with st.expander("Data Visualizer"):
        with st.form('generate Plot', clear_on_submit=True):
            df = vc.get_last_df(st.session_state.messages)
            selectbox_plot = st.selectbox(
                "Select a non-ID numeric column",
                eval(vc.get_last_num_column_string(st.session_state.messages)),
                index=None,
                placeholder="Select...",)

            options = st.multiselect(
                "Select category or label column(s)",
                vc.get_last_df_list(st.session_state.messages),
                placeholder="Select...",)
            
            user_message = st.text_input(
                "User Message",
                label_visibility="collapsed",
                placeholder="Add extra details (optional)"
            )

            submitted_plot = st.form_submit_button("Submit")
            if submitted_plot:
                if selectbox_plot and options:
                    st.write("Numeric column:", '*' + selectbox_plot + '*')
                    st.write("Category or label:", options)
                    options.append(selectbox_plot)
                    df_selected = df[df.columns.intersection(options)]
                    code = vc.generate_plotly_code_on_demand(df_selected, user_message)
                    fig = None
                
                    if code:
                        fig = vc.generate_plot_cached(code, df_selected)
                
                    if fig is not None:
                        st.session_state.messages.append({"role": "assistant", "content": fig, "type": "figure"})
                    else:
                        errorMessage = "I couldn't generate a chart"
                        st.session_state.messages.append({"role": "assistant", "content": errorMessage, "type": "error"})
                else:
                    st.write("Please complete all selections first")
                time.sleep(2)
                app_reload()
                     

    with st.expander('Output Settings'):
        st.toggle("Show Interpretation", value=True, key="show_interpretation")
        st.toggle("Show SQL", value=True, key="show_sql")
        st.toggle("Show Table", value=True, key="show_table")
        ###st.toggle("Show Plotly Code", value=False, key="show_plotly_code")
        st.toggle("Show Chart", value=True, key="show_chart")
        st.toggle("Show Summary", value=True, key="show_summary")
        #st.toggle("Show Follow-up Questions", value=False, key="show_followup")


    if st.button("Query Explanation", use_container_width=True):
        if st.session_state.explanation_open:
            st.empty()
            st.session_state.explanation_open = False
        else:
            
            last_sql = vc.get_last_sql(st.session_state.messages)

            if st.session_state.last_sql == last_sql:
                st.write(st.session_state.last_explanation)
                st.session_state.explanation_open = True
        
            else:
                if last_sql:
                    related_question = vc.get_related_question(last_sql, st.session_state.messages)
                    explanation = vc.generate_sql_explanation_on_demand(last_sql, related_question)

                    if explanation:
                        st.write(explanation)
                        st.session_state.last_explanation = explanation
                        st.session_state.explantion_open = True

                    else:
                        error_message = "I couldn't generate an explanation"
                        st.error(error_message)
                        st.session_state.explantion_open = True
                else:
                    st.write('Please generate a query first')
                    time.sleep(1)
                    app_reload()

            st.session_state.last_sql = last_sql



# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["type"] == "dataframe":
            st.dataframe(message["content"])
            continue
        elif message["type"] == "figure":
            st.plotly_chart(message["content"], key = id(message["content"]))
            continue
        elif message["type"] == "sql":
            st.code(message["content"],language="sql", line_numbers=True, wrap_lines=True)
            continue
        ###elif message["type"] == "python":
            ###st.code(message["content"],language="python", line_numbers=True, wrap_lines=True)
        elif message["type"] == "error":
            st.error(message["content"])
        else: 
            st.write(message["content"])

# React to user input
if prompt := st.chat_input("Ask me a question about your data"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt, "type": "text"})

    # Display assistant response in chat message container
    generate_response(prompt, True)


# Save chat history after each interaction
#vc.save_chat_history(st.session_state.messages)