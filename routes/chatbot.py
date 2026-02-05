from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError
from typing import Optional, List, Dict, Any
import crud
from models import User, Todo
from schemas import TodoCreate, TodoUpdate
from dependencies import get_db, get_current_user_optional

from groq import Groq
from groq.types.chat.chat_completion import ChatCompletionMessage
import os
import json
import dateparser 

router = APIRouter()

# Initialize Groq client
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError("GROQ_API_KEY environment variable not set.")
groq_client = Groq(api_key=groq_api_key)

class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    response: str
    history: List[Dict[str, Any]]

def _message_to_dict(message: ChatCompletionMessage) -> Dict[str, Any]:
    """Convert a ChatCompletionMessage to a JSON-serializable dictionary."""
    msg_dict = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        msg_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
    return msg_dict

async def execute_todo_action(action_type: str, args: dict, db: Session, current_user: Optional[User]) -> str:
    """Executes CRUD actions for todos based on the tool call."""
    if not current_user:
        return "You must be logged in to manage your to-do list. Please log in and try again."
    
    allowed_priorities = {"low", "medium", "high"}
    allowed_categories = {"work", "personal", "study", "home", "health", "shopping", "others"}

    # Date parsing for create and update actions
    if action_type in ["create_todo", "update_todo"] and "due_at" in args and isinstance(args["due_at"], str):
        parsed_date = dateparser.parse(args["due_at"])
        if parsed_date:
            args["due_at"] = parsed_date
        else:
            return f"Could not understand the date '{args['due_at']}'. Please use a more specific format (e.g., 'tomorrow at 5pm', '2026-02-10')."

    try:
        if action_type == "create_todo":
            # Set defaults and validate
            args.setdefault("priority", "low")
            args.setdefault("category", "others")

            if args.get("priority") not in allowed_priorities:
                return f"Invalid priority '{args['priority']}'. Allowed values are: {', '.join(allowed_priorities)}."
            if args.get("category") not in allowed_categories:
                return f"Invalid category '{args['category']}'. Allowed values are: {', '.join(allowed_categories)}."

            try:
                todo_data = TodoCreate(**args)
            except ValidationError as e:
                error_msg = e.errors()[0]['msg']
                return f"There was an issue creating the todo: {error_msg}"
            
            new_todo = crud.create_user_todo(db=db, todo=todo_data, user_id=current_user.id)
            return f"Successfully created todo: '{new_todo.title}'."

        elif action_type == "list_todos":
            todos = crud.get_todos(db=db, user_id=current_user.id)
            if not todos:
                return "You have no outstanding todos."
            todo_list_str = "\n".join([f"- {t.title} (Priority: {t.priority}, Category: {t.category}, Completed: {t.completed})" for t in todos])
            return f"Your todos:\n{todo_list_str}"

        elif action_type == "update_todo":
            original_title = args.get("original_title")
            if not original_title:
                return "Please provide the title of the todo you want to update."

            update_data = {k: v for k, v in args.items() if k not in ["original_title"]}
            if "new_title" in update_data:
                update_data["title"] = update_data.pop("new_title")
            
            # Validate priority and category if present
            if "priority" in update_data and update_data["priority"] not in allowed_priorities:
                return f"Invalid priority '{update_data['priority']}'. Allowed values are: {', '.join(allowed_priorities)}."
            if "category" in update_data and update_data["category"] not in allowed_categories:
                return f"Invalid category '{update_data['category']}'. Allowed values are: {', '.join(allowed_categories)}."

            if not update_data:
                return "Please provide at least one field to update (e.g., new title, description, due date, completed status, priority, or category)."

            matching_todos = crud.get_todos_by_title(db=db, title=original_title, user_id=current_user.id)
            
            if not matching_todos:
                return f"No todo found with title '{original_title}' for your account."
            elif len(matching_todos) > 1:
                matching_titles = [f"'{t.title}'" for t in matching_todos]
                return f"Multiple todos found with a title similar to '{original_title}'. Please provide the exact title you wish to update from the following: {', '.join(matching_titles)}."
            
            else:
                target_todo = matching_todos[0]
                try:
                    todo_update_schema = TodoUpdate(**update_data)
                    clean_update_data = todo_update_schema.dict(exclude_unset=True)
                except ValidationError as e:
                    error_msg = e.errors()[0]['msg']
                    return f"There was an issue updating the todo: {error_msg}"

                updated_todo = crud.update_user_todo(
                    db=db,
                    id=target_todo.id,
                    todo=clean_update_data,
                    user_id=current_user.id
                )
                
                update_fields = list(clean_update_data.keys())
                if 'completed' in update_fields and len(update_fields) == 1:
                    return f"Successfully marked '{updated_todo.title}' as complete."
                else:
                    return f"Successfully updated '{original_title}'. Changed fields: {', '.join(update_fields)}."

        elif action_type == "delete_todo":
            todo_title = args.get("title")
            if not todo_title:
                return "Please provide the title of the todo you want to delete."

            matching_todos = crud.get_todos_by_title(db=db, title=todo_title, user_id=current_user.id)
            if not matching_todos:
                return f"No todo found with title '{todo_title}' for your account."
            elif len(matching_todos) > 1:
                matching_titles = [f"'{t.title}'" for t in matching_todos]
                return f"Multiple todos found. Please provide the exact title: {', '.join(matching_titles)}."
            else:
                target_todo = matching_todos[0]
                crud.delete_user_todo(db=db, id=target_todo.id, user_id=current_user.id)
                return f"Successfully deleted todo: '{target_todo.title}'."

        else:
            return f"Unknown action: {action_type}"

    except Exception as e:
        print(f"An unexpected error occurred in execute_todo_action: {type(e).__name__}: {e}")
        return "Sorry, I ran into an unexpected issue."

@router.post("/chatbot", response_model=ChatResponse)
async def chat_with_bot(chat_message: ChatMessage, db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    """Handles the main chat logic, including conversation history and tool usage."""
    
    if current_user:
        system_prompt = f"""You are NestlyFlow's assistant, Flowy, speaking with {current_user.username}.
        - Your goal is to help the user manage their to-do list using the available tools. Be concise and friendly.
        - To update a task, use the `update_todo` tool. You MUST provide the `original_title` of the task you want to modify.
        - You can update the following fields: `description`, `due_at`, `completed` status, `priority`, or `category`.
        - When a user provides a category or priority, you must validate it against the allowed values.
        - Allowed priorities: 'low', 'medium', 'high'. If not specified, default to 'low'.
        - Allowed categories: 'work', 'personal', 'study', 'home', 'health', 'shopping', 'others'. If not specified, default to 'others'.
        - If the user specifies an invalid value for priority or category, you must inform them of the allowed options.
        - ONLY use the `new_title` parameter if the user explicitly asks to RENAME or CHANGE THE TITLE of the todo.
        - For marking tasks complete, use `update_todo` with `completed=True`.
        - If multiple todos match a title, you MUST ask for clarification. Do not mention "id".
        """
    else:
        system_prompt = """You are NestlyFlow's assistant, Flowy. The user is not logged in.
        - To-do list actions (create, update, list, delete) require login.
        - If the user asks to perform a to-do action, politely inform them they need to log in first.
        """

    tools = [
        {"type": "function", "function": {"name": "create_todo", "description": "Create a new to-do item.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "due_at": {"type": "string", "description": "Natural language due date (e.g., 'tomorrow at 5pm')."}, "priority": {"type": "string", "enum": ["low", "medium", "high"]}, "category": {"type": "string", "enum": ["work", "personal", "study", "home", "health", "shopping", "others"]}}, "required": ["title"]}}},
        {"type": "function", "function": {"name": "list_todos", "description": "List all to-do items for the user.", "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "update_todo", "description": "Update an existing to-do item.", "parameters": {"type": "object", "properties": {"original_title": {"type": "string", "description": "The current title of the todo to update."}, "new_title": {"type": "string", "description": "The new title for the todo."}, "description": {"type": "string", "description": "The new description for the todo."}, "due_at": {"type": "string", "description": "The new due date (e.g., 'in 2 days' or 'next Friday')."}, "completed": {"type": "boolean", "description": "Set to true to mark as complete, false to mark as incomplete."}, "priority": {"type": "string", "enum": ["low", "medium", "high"]}, "category": {"type": "string", "enum": ["work", "personal", "study", "home", "health", "shopping", "others"]}}, "required": ["original_title"]}}},
        {"type": "function", "function": {"name": "delete_todo", "description": "Delete a to-do item by its title.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}},
    ]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_message.history)
    messages.append({"role": "user", "content": chat_message.message})

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=messages, model="llama-3.3-70b-versatile", tools=tools, tool_choice="auto"
        )
        response_message = chat_completion.choices[0].message
        messages.append(_message_to_dict(response_message))

        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            tool_output = await execute_todo_action(function_name, function_args, db, current_user)
            
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": function_name, "content": str(tool_output)})

            second_chat_completion = groq_client.chat.completions.create(
                messages=messages, model="llama-3.3-70b-versatile", tool_choice="none"
            )
            final_response = second_chat_completion.choices[0].message.content
            messages.append({"role": "assistant", "content": final_response})
            return ChatResponse(response=final_response, history=messages)
        
        else:
            final_response = response_message.content or "I'm not sure how to respond to that."
            return ChatResponse(response=final_response, history=messages)

    except Exception as e:
        print(f"Error in chatbot: {type(e).__name__}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred with the chatbot: {e}")