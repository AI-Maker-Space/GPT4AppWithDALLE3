from langchain.agents import AgentExecutor, AgentType, initialize_agent
from langchain.agents.structured_chat.prompt import SUFFIX
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from tools import generate_image_tool

import chainlit as cl
from chainlit.action import Action
from chainlit.input_widget import Select, Switch, Slider


@cl.author_rename
def rename(orig_author):
    """
    Rename the author of messages as displayed in the "Thinking" section.

    This is useful to make the chat look more natural, or add some fun to it!
    """
    mapping = {
        "AgentExecutor": "The LLM Brain",
        "LLMChain": "The Assistant",
        "GenerateImage": "DALL-E 3",
        "ChatOpenAI": "GPT-4 Turbo",
        "Chatbot": "Coolest App",
    }
    return mapping.get(orig_author, orig_author)


@cl.cache
def get_memory():
    """
    This is used to track the conversation history and allow our agent to
    remember what was said before.
    """
    return ConversationBufferMemory(memory_key="chat_history")


@cl.on_chat_start
async def start():
    """
    This is called when the Chainlit chat is started!

    We can add some settings to our application to allow users to select the appropriate model, and more!
    """
    settings = await cl.ChatSettings(
        [
            Select(
                id="Model",
                label="OpenAI - Model",
                values=["gpt-3.5-turbo", "gpt-4-1106-preview"],
                initial_index=1,
            ),
            Switch(id="Streaming", label="OpenAI - Stream Tokens", initial=True),
            Slider(
                id="Temperature",
                label="OpenAI - Temperature",
                initial=0,
                min=0,
                max=2,
                step=0.1,
            ),
        ]
    ).send()
    await setup_agent(settings)


@cl.on_settings_update
async def setup_agent(settings):
    print("Setup agent with following settings: ", settings)

    # We set up our agent with the user selected (or default) settings here.
    llm = ChatOpenAI(
        temperature=settings["Temperature"],
        streaming=settings["Streaming"],
        model=settings["Model"],
    )

    # We get our memory here, which is used to track the conversation history.
    memory = get_memory()

    # This suffix is used to provide the chat history to the prompt.
    _SUFFIX = "Chat history:\n{chat_history}\n\n" + SUFFIX

    # We initialize our agent here, which is simply being used to decide between responding with text
    # or an image
    agent = initialize_agent(
        llm=llm,  # our LLM (default is GPT-4 Turbo)
        tools=[
            generate_image_tool
        ],  # our custom tool used to generate images with DALL-E 3
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,  # the agent type we're using today
        memory=memory,  # our memory!
        agent_kwargs={
            "suffix": _SUFFIX,  # adding our chat history suffix
            "input_variables": ["input", "agent_scratchpad", "chat_history"],
        },
    )
    cl.user_session.set("agent", agent)  # storing our agent in the user session


@cl.on_message
async def main(message: cl.Message):
    """
    This function is going to intercept all messages sent by the user, and
    move through our agent flow to generate a response.

    There are ultimately two different options for the agent to respond with:
    1. Text
    2. Image

    If the agent responds with text, we simply send the text back to the user.

    If the agent responds with an image, we need to generate the image and send
    it back to the user.
    """
    agent = cl.user_session.get("agent")
    cl.user_session.set("generated_image", None)

    res = await cl.make_async(agent.run)(
        input=message.content, callbacks=[cl.LangchainCallbackHandler()]
    )

    elements = []
    actions = []

    generated_image_name = cl.user_session.get("generated_image")
    generated_image = cl.user_session.get(generated_image_name)
    if generated_image:
        elements = [
            cl.Image(
                content=generated_image,
                name=generated_image_name,
                display="inline",
            )
        ]

    await cl.Message(content=res, elements=elements, actions=actions).send()
