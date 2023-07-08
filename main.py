import atexit
import os
import click
import datetime
import requests
import sys
import yaml
import json
from pathlib import Path
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv

# Load environment variables from .env file. This will read the file and set the environment variables.
load_dotenv()

# Define some constants and global variables. These are used throughout the script.
WORKDIR = Path(__file__).parent
CONFIG_FILE = Path(WORKDIR, "config.yaml")
HISTORY_FILE = Path(WORKDIR, ".history")
BASE_ENDPOINT = "https://api.openai.com/v1"
SAVE_FOLDER = "session-history"
SAVE_FILE = (
    "chatgpt-session-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
)

# Pricing rate per model, these are constants. 
PRICING_RATE = {
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-0613": {"prompt": 0.0015, "completion": 0.002},
    "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-0613": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-32k-0613": {"prompt": 0.06, "completion": 0.12},
}

# Initialize the messages history list
# It's mandatory to pass it at each API call in order to have a conversation
messages = []

# Initialize the token counters
prompt_tokens = 0
completion_tokens = 0

# Initialize the console
console = Console()

# Several function definitions follow here. These are used in the main part of the script below.
# They are separated out into functions for better readability and separation of concerns.
def load_config(config_file: str) -> dict:
    """
    Read a YAML config file and return its content as a dictionary
    """
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    return config

def create_save_folder() -> None:
    """
    Create the session history folder if it doesn't exist
    """
    if not os.path.exists(SAVE_FOLDER):
        os.mkdir(SAVE_FOLDER)

def add_markdown_system_message() -> None:
    """
    Try to force ChatGPT to always respond with well-formatted code blocks and tables if markdown is enabled.
    """
    instruction = "Always use code blocks with the appropriate language tags. If asked for a table, always format it using Markdown syntax."
    messages.append({"role": "system", "content": instruction})

def calculate_expense(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_pricing: float,
    completion_pricing: float,
) -> float:
    """
    Calculate the expense given the number of tokens and the pricing rates
    """
    expense = ((prompt_tokens / 1000) * prompt_pricing) + (
        (completion_tokens / 1000) * completion_pricing
    )
    return round(expense, 6)

def display_expense(model: str) -> None:
    """
    Given the model used, display the total tokens used and estimated expense
    """
    total_expense = calculate_expense(
        prompt_tokens,
        completion_tokens,
        PRICING_RATE[model]["prompt"],
        PRICING_RATE[model]["completion"],
    )
    console.print(
        f"\nTotal tokens used: [green bold]{prompt_tokens + completion_tokens}"
    )
    console.print(f"Estimated expense: [green bold]${total_expense}")

def start_prompt(session: PromptSession, config: dict) -> None:
    """
    Ask the user for input, build the request, and perform it
    """

    # TODO: Refactor to avoid using global variables
    global prompt_tokens, completion_tokens

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",  # Here's where we use the API Key from the environment variable
    }

    message = session.prompt(HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>"))

    if message.lower() == "/q":
        raise EOFError
    if message.lower() == "":
        raise KeyboardInterrupt

    messages.append({"role": "user", "content": message})

    body = {
        "model": config["model"],
        "temperature": config["temperature"],
        "messages": messages,
    }

    if "max_tokens" in config:
        body["max_tokens"] = config["max_tokens"]

    try:
        r = requests.post(
            f"{BASE_ENDPOINT}/chat/completions", headers=headers, json=body
        )
    except requests.ConnectionError:
        console.print("Connection error, try again...", style="red bold")
        messages.pop()
        raise KeyboardInterrupt
    except requests.Timeout:
        console.print("Connection timed out, try again...", style="red bold")
        messages.pop()
        raise KeyboardInterrupt

    if r.status_code == 200:
        response = r.json()

        message_response = response["choices"][0]["message"]
        usage_response = response["usage"]

        console.line()
        if config["markdown"]:
            console.print(Markdown(message_response["content"]))
        else:
            console.print(message_response["content"])

        messages.append(message_response)

        # Calculate tokens
        prompt_tokens += usage_response["prompt_tokens"]
        completion_tokens += usage_response["total_tokens"]

    elif r.status_code == 401:
        console.print("Unauthorized. Check your API key.", style="red bold")
        sys.exit(1)
    else:
        console.print(f"Error: {r.status_code}", style="red bold")
        sys.exit(1)

def load_context_files(context_files) -> None:
    """
    Load context files and append their content to the messages
    """
    for file in context_files:
        messages.append({"role": "system", "content": file.read()})

@click.command()
@click.option(
    "-c",
    "--context",
    "context",
    type=click.File("r"),
    help="Path to a context file",
    multiple=True,
)
@click.option("-m", "--model", "model", help="Set the model")
@click.option(
    "-ml", "--multiline", "multiline", is_flag=True, help="Use the multiline input mode"
)
def main(context, model, multiline) -> None:
    config = load_config(CONFIG_FILE)

    if model:
        config["model"] = model

    if multiline:
        config["multiline"] = multiline

    create_save_folder()

    if config["markdown"]:
        add_markdown_system_message()

    if context:
        load_context_files(context)

    atexit.register(display_expense, config["model"])

    history = FileHistory(HISTORY_FILE)
    session = PromptSession(history=history)

    while True:
        try:
            start_prompt(session, config)
        except (EOFError, KeyboardInterrupt):
            break

    with open(f"{SAVE_FOLDER}/{SAVE_FILE}", "w") as f:
        json.dump(messages, f, indent=2)

if __name__ == "__main__":
    main()
