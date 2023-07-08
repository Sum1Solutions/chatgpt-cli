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
                                                                                              
 # Load environment variables from .env file. This will read the file and set the environment                                                                               
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
                                                                                              
 # Initialize the console                                                                     
 console = Console()                                                                          
                                                                                              
 def load_config(config_file: str) -> dict:                                                   
     """                                                                                      
     Read a YAML config file and return its content as a dictionary                           
     """                                                                                      
     with open(config_file) as file:                                                          
         config = yaml.safe_load(file)                                                        
                                                                                              
     return config                                                                            
                                                                                              
 def create_save_folder() -> None:                                                            
     """                                                                                      
     Create the session history folder if it doesn't exist                                    
     """                                                                                      
     Path(SAVE_FOLDER).mkdir(parents=True, exist_ok=True)                                     
                                                                                              
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
                                                                                              
 def display_expense(prompt_tokens: int, completion_tokens: int, model: str) -> None:         
     """                                                                                      
     Given the model used, display the total tokens used and estimated expense                
     """                                                                                      
     total_tokens = prompt_tokens + completion_tokens                                         
     total_expense = calculate_expense(                                                       
         prompt_tokens,                                                                       
         completion_tokens,                                                                   
         PRICING_RATE[model]["prompt"],                                                       
         PRICING_RATE[model]["completion"],                                                   
     )                                                                                        
     console.print(f"\nTotal tokens used: [green bold]{total_tokens}")                        
     console.print(f"Estimated expense: [green bold]${total_expense}")                        
                                                                                              
 def construct_request(model: str, messages: list, config: dict) -> dict:                     
     """                                                                                      
     Construct the API request body                                                           
     """                                                                                      
     body = {                                                                                 
         "model": model,                                                                      
         "temperature": config["temperature"],                                                
         "messages": messages,                                                                
     }                                                                                        
                                                                                              
     if "max_tokens" in config:                                                               
         body["max_tokens"] = config["max_tokens"]                                            
                                                                                              
     return body                                                                              
                                                                                              
 def send_api_request(headers: dict, body: dict) -> dict:                                     
     """                                                                                      
     Send the chat completion API request and return the response                             
     """                                                                                      
     try:                                                                                     
         response = requests.post(                                                            
             f"{BASE_ENDPOINT}/chat/completions", headers=headers, json=body                  
         )                                                                                    
         response.raise_for_status()                                                          
         return response.json()                                                               
     except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:            
         console.print(f"API request error: {e}", style="red bold")                           
         sys.exit(1)                                                                          
                                                                                              
 def start_prompt(session: PromptSession, config: dict, headers: dict, messages: list,        
 prompt_tokens: int, completion_tokens: int) -> None:                                         
     """                                                                                      
     Ask the user for input, build the request, and perform it                                
     """                                                                                      
     message = session.prompt(HTML(f"<b>[{prompt_tokens + completion_tokens}] >>> </b>"))     
                                                                                              
     if message.lower() == "/q":                                                              
         raise EOFError                                                                       
     if message.lower() == "":                                                                
         raise KeyboardInterrupt                                                              
                                                                                              
     messages.append({"role": "user", "content": message})                                    
                                                                                              
     body = construct_request(config["model"], messages, config)                              
                                                                                              
     response = send_api_request(headers, body)                                               
                                                                                              
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
                                                                                              
     return prompt_tokens, completion_tokens                                                  
                                                                                              
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
         messages.append({"role": "system", "content": "Always use code blocks with the       
 appropriate language tags. If asked for a table, always format it using Markdown syntax."})  
                                                                                              
     for file in context:                                                                     
         messages.append({"role": "system", "content": file.read()})                          
                                                                                              
     atexit.register(display_expense, prompt_tokens, completion_tokens, config["model"])      
                                                                                              
     history = FileHistory(HISTORY_FILE)                                                      
     session = PromptSession(history=history)                                                 
                                                                                              
     prompt_tokens = 0                                                                        
     completion_tokens = 0                                                                    
                                                                                              
     headers = {                                                                              
         "Content-Type": "application/json",                                                  
         "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",                            
     }                                                                                        
                                                                                              
     while True:                                                                              
         try:                                                                                 
             prompt_tokens, completion_tokens = start_prompt(                                 
                 session, config, headers, messages, prompt_tokens, completion_tokens         
             )                                                                                
         except (EOFError, KeyboardInterrupt):                                                
             break                                                                            
                                                                                              
     with open(f"{SAVE_FOLDER}/{SAVE_FILE}", "w") as f:                                       
         json.dump(messages, f, indent=2)                                                     
                                                                                              
 if __name__ == "__main__":                                                                   
     main()                               
