from flask import Flask, request, jsonify
import asyncio
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import concurrent.futures
from typing import List, Dict, Any

load_dotenv()

app = Flask(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL')

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not MCP_SERVER_URL:
    raise ValueError("MCP_SERVER_URL environment variable is required")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

class MCPManager:
    def __init__(self, server_url):
        self.server_url = server_url
        self.transport = StreamableHttpTransport(server_url)
        self.client = Client(transport=self.transport)
        self.available_tools = []
    
    async def get_available_tools(self):
        """Fetch available tools from MCP server"""
        try:
            async with self.client:
                tools = await self.client.list_tools()
                self.available_tools = []
                
                for tool in tools:
                    tool_schema = getattr(tool, 'inputSchema', None)
                    
                    if tool_schema and hasattr(tool_schema, 'get'):
                        properties = tool_schema.get('properties', {})
                        required = tool_schema.get('required', [])
                    else:
                        properties = {}
                        required = []
                    
                    if 'instructions' in required:
                        required = [r for r in required if r != 'instructions']
                    
                    # ChatCompletion required format
                    tool_definition = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required
                            }
                        }
                    }
                    
                    self.available_tools.append(tool_definition)
                
                return self.available_tools
        except Exception as e:
            print(f"Error fetching tools: {e}")
            return []
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given parameters"""
        try:
            async with self.client:
                mcp_parameters = {
                    "instructions": f"Execute the {tool_name} tool with the following parameters",
                    **parameters  
                }
                
                result = await self.client.call_tool(tool_name, mcp_parameters)
               
                if result and len(result) > 0:
                    if hasattr(result[0], 'text'):
                        try:
                            return json.loads(result[0].text)
                        except json.JSONDecodeError:
                            return {"result": result[0].text}
                    else:
                        return {"result": str(result[0])}
                return {"result": "No result returned"}
        except Exception as e:
            print(f"Error executing tool {tool_name}: {e}")
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}
    
    async def execute_tools_concurrently(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tools concurrently"""
        tasks = []
        
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            function_args = json.loads(tool_call['function']['arguments'])
            
            # Create async task for each tool execution
            task = asyncio.create_task(
                self.execute_tool(function_name, function_args)
            )
            tasks.append({
                'task': task,
                'tool_call': tool_call,
                'function_name': function_name,
                'function_args': function_args
            })
        
        # Wait for all tasks to complete
        results = []
        for task_info in tasks:
            try:
                result = await task_info['task']
                results.append({
                    'tool_call_id': task_info['tool_call']['id'],
                    'function_name': task_info['function_name'],
                    'function_args': task_info['function_args'],
                    'result': result,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'tool_call_id': task_info['tool_call']['id'],
                    'function_name': task_info['function_name'],
                    'function_args': task_info['function_args'],
                    'result': {"error": f"Failed to execute {task_info['function_name']}: {str(e)}"},
                    'success': False
                })
        
        return results

# Initialize MCP Manager
mcp_manager = MCPManager(MCP_SERVER_URL)

def run_async(coro):
    """Helper function to run async code in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Get user message from request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No message provided"}), 400
        
        # Step 1: Get available tools from MCP server
        available_tools = run_async(mcp_manager.get_available_tools())
        
        # Step 2: Prepare chat completion with function calling
        messages = [
            {"role": "system", "content": "You are a helpful assistant that can use various tools to help users. When a user asks for something that requires multiple tools, you can call multiple functions simultaneously. Always provide clear, friendly responses with proper formatting. If you create or access any links, format them as clickable markdown links."}
        ]
        messages.extend(data)
        
        # Step 3: Call OpenAI Chat Completion with functions
        if available_tools:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=available_tools,
                tool_choice="auto"
            )
        else:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
        
        assistant_message = response.choices[0].message
        
        # Step 4: Check if tools were called
        if assistant_message.tool_calls:
            print(f"Number of tool calls: {len(assistant_message.tool_calls)}")
            
            # Convert tool calls to list of dictionaries for processing
            tool_calls_list = []
            for tool_call in assistant_message.tool_calls:
                tool_calls_list.append({
                    'id': tool_call.id,
                    'type': tool_call.type,
                    'function': {
                        'name': tool_call.function.name,
                        'arguments': tool_call.function.arguments
                    }
                })
                print(f"Tool call: {tool_call.function.name} with args: {tool_call.function.arguments}")
            
            # Step 5: Execute all tools concurrently
            tool_results = run_async(mcp_manager.execute_tools_concurrently(tool_calls_list))
            
            # Step 6: Add assistant message with tool calls to conversation
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in assistant_message.tool_calls
                ]
            })
            
            # Step 7: Add tool results to conversation
            for result_info in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": result_info['tool_call_id'],
                    "content": json.dumps(result_info['result'])
                })
                
                if result_info['success']:
                    print(f"✓ {result_info['function_name']} executed successfully")
                else:
                    print(f"✗ {result_info['function_name']} failed: {result_info['result']}")
            
            # Step 8: Add formatting instructions
            messages.append({
                "role": "system",
                "content": "Format your response in a user-friendly way. If there are any URLs in the tool results, format them as clickable markdown links. Provide a clear, concise summary of what was accomplished with each tool. If multiple tools were executed, organize the results clearly. Don't show raw JSON or technical details unless specifically requested."
            })
            
            # Step 9: Get final response from OpenAI
            final_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            
            # Return the formatted response with execution summary
            execution_summary = {
                "tools_executed": len(tool_results),
                "successful_executions": sum(1 for r in tool_results if r['success']),
                "failed_executions": sum(1 for r in tool_results if not r['success']),
                "concurrent_execution": len(tool_results) > 1
            }
            
            return jsonify({
                "response": final_response.choices[0].message.content,
                "execution_summary": execution_summary
            })
        
        else:
            # No function was called, return regular text response
            return jsonify({
                "response": assistant_message.content
            })
    
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tools', methods=['GET'])
def get_tools():
    """Endpoint to get available tools"""
    try:
        tools = run_async(mcp_manager.get_available_tools())
        return jsonify({
            "tools": tools,
            "count": len(tools)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "mcp_server_url": MCP_SERVER_URL,
        "tools_available": len(mcp_manager.available_tools)
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Flask app on port {port}")
    print(f"MCP Server URL: {MCP_SERVER_URL}")
    print(f"Debug mode: {debug_mode}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)