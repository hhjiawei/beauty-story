from deepagents import create_deep_agent
from tools import web_search

"""
故事架构师的deep agent

"""




agent = create_deep_agent(
    model='',

    tools=[web_search],
    system_prompt=research_instructions
)




