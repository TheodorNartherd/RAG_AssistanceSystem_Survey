import pandas as pd

class VN_session():
    def __init__(self,history=None):
        if history is None:
            self._history = []
        else:
            self._history = history

    
    def get_history(self) -> list:
        return self._history

    def set_history(self,history: list):
        self._history = history

    def add_turnToHistory(self, questionSQLpair: dict):
        self._history.append(questionSQLpair)

    def add_sqlToLastTurn(self, sql:str):
        lastDict = self._history[-1]
        lastDict['query'] = sql
        self._history[-1] = lastDict

    def add_summaryToLastTurn(self, summary:str):
        lastDict = self._history[-1]
        lastDict['summary'] = summary
        self._history[-1] = lastDict

    def add_dataframeToLastTurn(self, df: pd.DataFrame):
        lastDict = self._history[-1]
        lastDict['dataframe'] = df
        self._history[-1] = lastDict

    def add_interpretationToLastTurn(self, interpretation:str):
        lastDict = self._history[-1]
        lastDict['interpretation'] = interpretation
        self._history[-1] = lastDict
