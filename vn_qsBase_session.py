from vanna.qdrant import Qdrant_VectorStore
from vanna.openai import OpenAI_Chat

from vanna.types import TrainingPlan
from dotenv import load_dotenv
import os

import sqlite3
import pandas as pd

from vn_session import VN_session
import openai_cookbook as oc

import re
import ast

load_dotenv('.env')

class VN_QsBase(Qdrant_VectorStore, OpenAI_Chat):
    def __init__(self, config=None):
        Qdrant_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)

        self._session = VN_session()
        self.model = config.get("model")


    # Prompt-Modul
    ## Table Representation
    def convert_ddlToSchema(self,ddl:str) -> str:
        chrList = ['"',"'","`", '\t', '\\t']
        for chr in chrList:
            ddl = ddl.replace(chr,' ')

        code_lines = ddl.split('\n')
        schema = code_lines[0].strip().removeprefix('CREATE TABLE')
        code_lines = code_lines[1:]
        for cl in code_lines:
            if cl.startswith(','):
                cl = cl.replace(',', '')
            cl = cl.strip()
            if cl.upper().startswith('PRIMARY KEY'):
                continue
            if ('FOREIGN KEY' in cl.upper()  or len(cl)==1): 
                schema +=cl.replace('( ', '(').replace(' )', ')') + ' '
            else:
                firstWord = cl.split(' ')[0]
                schema += firstWord + ', '

        if not(schema.strip().endswith(')')):
            schema = schema + ')'
        result = ')'.join(schema.rsplit(', )', 1)).strip()
    
        return result
    
    def get_exampleValues(self, tbl_name, db_name) -> str:
        self.connect_to_sqlite(os.getenv('dbLoc') + '/' + db_name + '/' + db_name + '.sqlite')
        sql = 'SELECT * FROM ' + tbl_name + ' ORDER BY RANDOM() LIMIT 2'
        example_dict = self.run_sql(sql).to_dict('list')
        return 'Value-Examples: ' + str(example_dict).replace('{', '').replace('}', '')

    def add_ddl(self, ddl: str, **kwargs) -> str:
        schema = self.convert_ddlToSchema(ddl)
        exampleValues = self.get_exampleValues(kwargs.get('tbl_name'), kwargs.get('db_name'))
        schema += ' \n' + exampleValues
        return super().add_ddl(schema)
    
    def train(
        self,
        question: str = None,
        sql: str = None,
        ddl: str = None,
        documentation: str = None,
        plan: TrainingPlan = None,
        **kwargs
    ) -> str:
        if ddl:
            print("Adding ddl:", ddl)
            return self.add_ddl(ddl,**kwargs)
        else: 
            super().train(question,sql,documentation,plan)

    
    ## Prompt Representation
    #   Override of VannaBase. Newly implemented according to (Gao et al., 2023)
    def get_sql_prompt(
        self,
        initial_prompt : str,
        question: str,
        question_sql_list: list,
        ddl_list: list,
        doc_list: list,
        utterance_list: list,
        **kwargs,
    ):
        """
        Example:
        ```python
        vn.get_sql_prompt(
            question="What are the top 10 customers by sales?",
            question_sql_list=[{"question": "What are the top 10 customers by sales?", "sql": "SELECT * FROM customers ORDER BY sales DESC LIMIT 10"}],
            ddl_list=["CREATE TABLE customers (id INT, name TEXT, sales DECIMAL)"],
            doc_list=["The customers table contains information about customers and their sales."],
        )

        ```

        This method is used to generate a prompt for the LLM to generate SQL.

        Args:
            question (str): The question to generate SQL for.
            question_sql_list (list): A list of questions and their corresponding SQL statements.
            ddl_list (list): A list of DDL statements.
            doc_list (list): A list of documentation.

        Returns:
            any: The prompt for the LLM to generate SQL.
        """

        if initial_prompt is None:
            initial_prompt = f"You are a {self.dialect} expert. Generate {self.dialect} SQL query only and with no explanation. Instead of '*' always name all the columns. If there are duplicate column names, use aliases by using the table-name as a prefix with an '_' as a seperator. \n"

        initial_prompt = self.add_ddl_to_prompt(
            initial_prompt, ddl_list, max_tokens=self.max_tokens
        )

        if self.static_documentation != "":
            doc_list.append(self.static_documentation)

        initial_prompt = self.add_documentation_to_prompt(
            initial_prompt, doc_list, max_tokens=self.max_tokens
        )

        message_log = [self.system_message(initial_prompt)]

        if len(question_sql_list) > 0:
            message_log.append(self.system_message('Some example questions and corresponding SQL queries are provided based on similar problems:'))

        for example in question_sql_list:
            if example is None:
                print("example is None")
            else:
                if example is not None and "question" in example and "sql" in example:
                    message_log.append(self.user_message(example["question"]))
                    message_log.append(self.assistant_message(example["sql"]))

        if len(utterance_list) > 0:
            message_log.append(self.system_message('Past interactions in this session: '))
        
        for utterance in utterance_list:
            if utterance is None:
                print("no history")
            else:
                if utterance is not None and "question" in utterance and "query" in utterance:
                    message_log.append(self.user_message(utterance["question"]))
                    if utterance["query"] is not None:
                        message_log.append(self.assistant_message(utterance["query"]))
                    if utterance["summary"] is not None:
                        message_log.append(self.assistant_message("Result-Summary: " + utterance["summary"]))
        
        message_log.append(self.system_message(f"The System has interpreted the user-question as:\n'{kwargs.get('plan')}'\n\n. Based on that interpretation, generate a SQL-Query for the following:"))
        message_log.append(self.user_message(question))

        return message_log
    
    def add_ddl_to_prompt(
        self, initial_prompt: str, ddl_list: list[str], max_tokens: int = 14000
    ) -> str:
        if len(ddl_list) > 0:
            initial_prompt += '\n' + f"{self.dialect} SQL tables, with their properties:\n\n"

            for ddl in ddl_list:
                if (
                    self.str_to_approx_token_count(initial_prompt)
                    + self.str_to_approx_token_count(ddl)
                    < max_tokens
                ):
                    initial_prompt += f"{ddl}\n"

        return initial_prompt
    """
    # Schema-Linking-Modul
    def get_related_ddl(self, question: str, **kwargs) -> list:
        keywordList = self.get_keywords(question)
        ddl_list = []
        for keyword in keywordList:
            results = self._client.query_points(
            self.ddl_collection_name,
            query=self.generate_embedding(keyword),
            limit=2,
            with_payload=True,
            ).points
            result_list = [result.payload["ddl"] for result in results]
            ddl_list.extend(result_list)

        return list(set(ddl_list))

    def get_keywords(self,question):
        keywords = self.kw_model.extract_keywords(question)
        res_list = [x[0] for x in keywords]
        return res_list
    """
    
    # Correction-Modul
    def generate_and_correct_sql(self, question: str, **kwargs) -> str:
        sql = self.generate_sql(question, **kwargs)
        if not self.is_sql_valid(sql):
            return "", "Not a text-to-sql-question"
        
        db_id = kwargs.get('db_id')
        db_path = os.getenv('dbLoc') + '/' + db_id + '/' + db_id + '.sqlite'
        executable, message = self.check_sql(sql,db_path)
        
        if executable:
            return sql, message
        else:
            self.log(title="SQL Correction needed: 1. Attempt", message=message)
            return self.correct_sql(question, sql, message, db_path, 1, **kwargs)


    def check_sql(self,predicted_sql,db_path):
        conn = sqlite3.connect(db_path)
        conn.text_factory = bytes
        cursor = conn.cursor()
        try:
            cursor.execute(predicted_sql)
        except Exception as e:
            return False, str(e)
    
        predicted_res = cursor.fetchall()
        if len(predicted_res) > 0:
            return True, None
        else:
            return False, "sql returns no value"
        
    def correct_sql(self, question, sql, message, db_path, attempt, **kwargs) -> str:
        correction_prompt = self.get_correction_prompt(question, sql, message, **kwargs)
        self.log(title="Correction Prompt", message=correction_prompt)
        corrected_llm_response = self.submit_prompt(correction_prompt)
        corrected_sql = self.extract_dict_value(corrected_llm_response, "corrected_SQL")
        executable, new_message = self.check_sql(corrected_sql, db_path)
        if executable or attempt == 2:
            return self.extract_sql(corrected_sql), new_message
        else:
            self.log(title="SQL Correction needed: " + str(attempt + 1) + '. Attempt', message=new_message)
            return self.correct_sql(question, corrected_sql, new_message, db_path, attempt + 1, **kwargs) 

    def get_correction_prompt(self, question, sql, message, **kwargs) -> str:
        initial_prompt = f"You are a {self.dialect} expert. There is a SQL query generated based on the following Database Schema to respond to the Question. Executing this SQL has resulted in an error and you need to fix it based on the error message, while following the system-interpetation of the question. \n"
        
        ddl_list = self.get_related_ddl(question)
        initial_prompt = self.add_ddl_to_prompt(
            initial_prompt, ddl_list, max_tokens=self.max_tokens
        )

        initial_prompt += '\n' + f"Question:\n{question} \n"
        initial_prompt += '\n' + f"System-Interpretation:\n{kwargs.get('plan')} \n"
        initial_prompt += '\n' + f"Executed SQL:\n{sql} \n"
        initial_prompt += '\n' + f"Error Message:\n{message} \n"

        initial_prompt += '\n Please respond with a Python-Dictionary storing the two keys "chain_of_thought_reasoning" and "corrected_SQL" written as a one-liner. \n'

        message_log = [self.system_message(initial_prompt)]
        
        # Added for multi-turn-functionality
        #utterance_list = self._session.get_history()[-6:-1]
        #if len(utterance_list) > 0:
            #message_log.append(self.system_message('Past interactions in this session: '))
            
        #for utterance in utterance_list:
            #if utterance is None:
                #print("no history")
            #else:
                #if utterance is not None and "question" in utterance and "query" in utterance:
                    #message_log.append(self.user_message(utterance["question"]))
                    #if utterance["query"] is not None:
                        #message_log.append(self.assistant_message(utterance["query"]))
                    #if utterance["summary"] is not None:
                        #message_log.append(self.assistant_message("Result-Summary: " + utterance["summary"]))

        return message_log
    
    def extract_dict_value(self, llm_response: str, key: str):

        pattern = r'\{.*?\}'

        matches = re.findall(pattern, llm_response, re.DOTALL)
        for match in matches:
            try:
                result = ast.literal_eval(match)
                if isinstance(result, dict):
                    return result[key]
            except (ValueError, SyntaxError):
                continue

        print("No valid dictionary found.")
        return None


    # Added to stay within the context-window
    def generate_summary(self, question: str, df: pd.DataFrame, **kwargs) -> str:
        summary_prompt = self.get_summary_prompt(question, df, **kwargs)
        summary = self.submit_prompt(summary_prompt, **kwargs)
        return summary

    def get_summary_prompt(self, question: str, df: pd.DataFrame, **kwargs) -> str:
        alternatives = kwargs.get('alternatives')
        self.log(title="Alternatives", message=str(alternatives))

        message_log = [
            self.system_message(
                f"You are a helpful data assistant. The user asked the question: '{question}'\n\nThe following is a pandas DataFrame with the results of the query: \n{df[:100].to_markdown()}\n\n"
            ),
            self.user_message(
                "Briefly summarize the data based on the question that was asked. " \
                f"Start a new paragraph before briefly summarizing the following alternatives without asking the user to choose. Instead, invite the user to let you know, if they'd like to see the result for any of them: {str(alternatives)} " \
                "Do not respond with any additional explanation beyond the summary and invitation." +
                self._response_language()
            ),
        ]
        num_tokens = oc.num_tokens_from_messages(message_log, self.model)
        context_window = self.get_context_window(self.model)
        if num_tokens < (context_window / 2):
            return message_log
        else: 
            row = len(df)
            reduce = round(row * 0.75)
            return self.get_summary_prompt(question, df[:reduce])

    def get_context_window(self, model_name):
        context_windows = {
            'gpt-3.5-turbo': 4096,
            'gpt-3.5-turbo-16k': 16384,
            'gpt-4': 8192,
            'gpt-4-32k': 32768,
            'gpt-4-turbo': 128000,
            'gpt-4o': 128000,
            'gpt-4o-mini': 128000,
            'gpt-4.1': 1000000,
            'gpt-4.1-mini': 1000000,
        }
        return context_windows.get(model_name)

    # For multi-turn szenario
    def setUp_newSession(self):
        self._session = VN_session()
    
    def get_currentSession(self) -> VN_session:
        return self._session
    
    def generate_sql(self, question: str, allow_llm_to_see_data=False, **kwargs) -> str:
        
        if self.config is not None:
            initial_prompt = self.config.get("initial_prompt", None)
        else:
            initial_prompt = None
        question_sql_list = self.get_similar_question_sql(question, **kwargs)
        ddl_list = self.get_related_ddl(question, **kwargs)
        doc_list = self.get_related_documentation(question, **kwargs)
        utterance_list = self._session.get_history()[-6:-1]
        prompt = self.get_sql_prompt(
            initial_prompt=initial_prompt,
            question=question,
            question_sql_list=question_sql_list,
            ddl_list=ddl_list,
            doc_list=doc_list,
            utterance_list = utterance_list,
            **kwargs,
        )
        self.log(title="SQL Prompt", message=prompt)
        llm_response = self.submit_prompt(prompt, **kwargs)
        self.log(title="LLM Response", message=llm_response)
                                        
        return self.extract_sql(llm_response)
    

    # Revision-Modul
    def check_sql_for_release(self, predicted_sql, db_path):
        conn = sqlite3.connect(db_path)
        conn.text_factory = bytes
        cursor = conn.cursor()
        try:
            cursor.execute(predicted_sql)
        except Exception as e:
            return False, predicted_sql, str(e)
    
        return True, predicted_sql, None
    
    # Interpretation-Modul
    def get_interpretation(self, question, **kwargs):
        ddl_list = self.get_all_ddl()
        utterance_list = self._session.get_history()[-6:-1]
        prompt = self.get_interpretation_prompt(question, ddl_list, utterance_list)
        llm_response = self.submit_prompt(prompt, **kwargs)
        plan = self.extract_dict_value(llm_response, "most_likely")
        alternatives = self.extract_dict_value(llm_response, "alternatives")
        print(alternatives)
        return plan, alternatives

    def get_interpretation_prompt(self, question, ddl_list, utterance_list):
        initial_prompt = "You are a Database Expert System specialized in the {self.dialect} dialect. Your task is to interpret the user's natural language question, describe the most likely interpretation and generate a Python-list of other plausible interpretations or intentions behind it. These interpretations will serve as alternative plans for generating a SQL query in later steps. Use the provided database-schema and the conversation-context to guide your analysis. \n"

        initial_prompt += '\n Please respond with a Python-Dictionary storing the three keys "chain_of_thought_reasoning", "most_likely" and "alternatives" written as a one-liner. '
        initial_prompt += '\n The value for "most_likely" should be the interpretation that is going to satisfy the user best and not include any extra information. '
        initial_prompt += '\n The value for "alternatives" must be a Python-list. The values for that list needs to be brief description of the other alternatives and not include any extra information. If there is only one clear primary interpretation, return [] \n'

        initial_prompt = self.add_ddl_to_prompt(
            initial_prompt, ddl_list, max_tokens=self.max_tokens
        )

        message_log = [self.system_message(initial_prompt)]
        
        # Added for multi-turn-functionality
        if len(utterance_list) > 0:
            message_log.append(self.system_message('Past interactions in this session: '))
            
        for utterance in utterance_list:
            if utterance is None:
                print("no history")
            else:
                if utterance is not None and "question" in utterance and "query" in utterance:
                    message_log.append(self.user_message(utterance["question"]))
                    if utterance["query"] is not None:
                        message_log.append(self.assistant_message(utterance["query"]))
                    if utterance["summary"] is not None:
                        message_log.append(self.assistant_message("Result-Summary: " + utterance["summary"]))
        
        message_log.append(self.system_message('Classify the following question:'))
        message_log.append(self.user_message(question))

        return message_log


# Additional Functionalities
    # Suggest a Question
    def generate_questions(self, **kwargs) -> list[str]:
        ddl_list = self.get_all_ddl()
        utterance_list = self._session.get_history()[-5:]
        prompt = self.get_question_prompt(ddl_list, utterance_list, **kwargs)
        llm_response = self.submit_prompt(prompt, **kwargs)
        return self.extract_questionList(llm_response)
    
    def get_all_ddl(self):
        trainingData = self.get_training_data()
        ddlData = trainingData[trainingData.training_data_type=='ddl']
        return ddlData['content'].tolist()
    
    def get_question_prompt(self,ddl_list, utterance_list, **kwargs):
        initial_prompt = f"Generate 5 questions about the following database, that can be answered with a SQL query. This means that the question should have specific values and can be given to a NLIDB without any changes. Consider what users asked in the past and suggest questions that help them explore the database. "
        initial_prompt += "Return just the question without any additional explanation. The ouput needs to be in one python-list written as a one-liner."
        initial_prompt = self.add_ddl_to_prompt(
            initial_prompt, ddl_list, max_tokens=self.max_tokens
        )

        message_log = [self.system_message(initial_prompt)]

        if len(utterance_list) > 0:
            message_log.append(self.system_message('Past interactions in this session: '))
        
        for utterance in utterance_list:
            if utterance is None:
                print("no history")
            else:
                if utterance is not None and "question" in utterance and "query" in utterance:
                    message_log.append(self.user_message(utterance["question"]))
                    if utterance["query"] is not None:
                        message_log.append(self.assistant_message(utterance["query"]))
                    if utterance["summary"] is not None:
                        message_log.append(self.assistant_message("Result-Summary: " + utterance["summary"]))

        return message_log
    
    def extract_questionList(self, llm_response: str) -> list[str]:

        start = "["
        end = "]"

        # Find the index of the start substring
        idx1 = llm_response.find(start)

        # Find the index of the end substring, starting after the start substring
        idx2 = llm_response.find(end, idx1 + len(start))

        # Check if both delimiters are found and extract the substring between them
        if idx1 != -1 and idx2 != -1:
            res = llm_response[idx1 + len(start):idx2]
            return eval('[' + res + ']')

        else:
            print("Delimiters not found")

    # Generate Plot
    def should_generate_chart(self, df: pd.DataFrame) -> bool:
        if super().should_generate_chart(df):
            num_columns = list(df.select_dtypes(include=['number']))
            return any(not col.lower().endswith("id") for col in num_columns)
        else:
            return False
        
    def generate_plotly_code_on_demand(self, df, message, **kwargs):
        system_msg = f"The following is a pandas DataFrame 'df': \n{df}"

        message_log = [
            self.system_message(system_msg),
            self.user_message(
                "Can you generate the Python plotly code to chart the results of the dataframe? Assume the data is in a pandas dataframe called 'df'. If there is only one value in the dataframe, use an Indicator. Respond with only Python code. Do not answer with any explanations -- just the code."
            ),
        ]

        if(message):
            message_log.append(self.system_message("Take especially the following user-message into consideration:"))
            message_log.append(self.user_message(message))


        plotly_code = self.submit_prompt(message_log, kwargs=kwargs)

        return self._sanitize_plotly_code(self._extract_python_code(plotly_code))
    
    def generate_sql_explanation_on_demand(self, sql, related_question, **kwargs):
        message_log = [
            self.system_message(
                f"You are a helpful data assistant. The user has asked the question: '{related_question}'\n\nThe following is the generated query: \n{sql}\n\n"
            ),
            self.system_message(
                "Briefly explain the query based on the question that was asked. While keeping it as short as possible, explain each clause-type and subselect. Do not respond with any additional information beyond the explanation." +
                self._response_language()
            ),
        ]

        explanation = self.submit_prompt(message_log, **kwargs)

        return explanation
    
    def generate_error_response(self, question, message, **kwargs):
        message_log = [
            self.system_message(
                f"You are a helpful data assistant. In order to generate a sql-query the user has asked the question: '{question}'\n\nThe following is the message of the system or database: \n{message}\n\n"
            ),
            self.system_message(
                "Briefly explain why a SQL couldn't be generated for that question. " \
                "If a user asked a question unrelated to text-to-sql, make a cheeky, but professional remark to their question. Refer them afterwards to the tools 'Question Suggestion', 'Data Structure' and 'Table Preview' on the left, if they need inspiration." \
                "If a sql couldn't be generated due to an execution error, apologize for the wait and suggest a different wording for that question." \
                "Do not respond with any additional information beyond the task that was given." +
                self._response_language()
            ),
        ]

        explanation = self.submit_prompt(message_log, **kwargs)

        return explanation
    
    def genenerate_interpretation_respond(self, question, plan, **kwargs):
        message_log = [
            self.system_message(
                f"You are a helpful data assistant. The user has asked the following question:\n'{question}'\n\nThe system has interpreted the question as: \n{plan}\n\n"
            ),
            self.system_message(
                "Rephrase this interpretation into a short, friendly explanation that confirms how the system understood the user's request. " \
                "Use natural, conversational language. Do not provide any additional information, include any questions or ask for confirmation." +
                self._response_language()
            ),
        ]

        interpretation_respond = self.submit_prompt(message_log, **kwargs)

        return interpretation_respond