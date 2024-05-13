from flask import Flask, request, render_template, jsonify, g  
import pyodbc  
from openai import AzureOpenAI  
import json  
  
app = Flask(__name__)  
  
# Directly defined credentials (Consider using environment variables for production)  
AZURE_OPENAI_ENDPOINT = "https://azureopenai-photon.openai.azure.com/"  
AZURE_OPENAI_API_KEY = "82767c3fcf7b4bd4b916b98928a22f2b"  
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"  
  
SQL_SERVER = "photonhrmsserver.database.windows.net"  
SQL_DB = "photonhrmsdatabase"  
SQL_USERNAME = "Admini"  
SQL_PASSWORD = "Photon@5215"
  
# Initialize Azure OpenAI client with your credentials  
client = AzureOpenAI(  
    azure_endpoint=AZURE_OPENAI_ENDPOINT,  
    api_key=AZURE_OPENAI_API_KEY,  
    api_version=AZURE_OPENAI_API_VERSION  
)  
  
@app.before_request  
def before_request():  
    g.db_conn = pyodbc.connect(  
        f"Driver={{ODBC Driver 18 for SQL Server}};"  
        f"Server=tcp:{SQL_SERVER},1433;"  
        f"Database={SQL_DB};"  
        f"Uid={SQL_USERNAME};"  
        f"Pwd={SQL_PASSWORD};"  
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"  
    )  
    g.cursor = g.db_conn.cursor()  
  
@app.teardown_request  
def teardown_request(exception=None):  
    db_conn = getattr(g, 'db_conn', None)  
    if db_conn is not None:  
        db_conn.close()  
  
def fetch_column_names(table_name="Employee"):  
    g.cursor.execute(f"SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'{table_name}'")  
    columns = [row[3] for row in g.cursor.fetchall()]  
    return columns  
  
def nlp_to_sql(nlp_query, table_name="Employee"):  
    columns = fetch_column_names(table_name)  
    columns_str = ", ".join(columns)  
      
    prompt_messages = [  
        {"role": "system", "content": f"Given the table '{table_name}' with columns {columns_str}, convert the following natural language query into an SQL query considering partial matches and relevant columns. Use TOP and LIKE for partial matches and focus on columns that are likely targets based on the query's context:"},  
        {"role": "user", "content": nlp_query}  
    ]  
      
    response = client.chat.completions.create(  
        model="gpt-4-turbo",  
        messages=prompt_messages,  
        temperature=0.7,  
        max_tokens=4096  
    )  
      
    content = response.choices[0].message.content.strip()  
      
    if "```sql" in content and "```" in content.split("```sql")[1]:  
        sql_query = content.split("```sql")[1].split("```")[0].strip()  
    else:  
        sql_query = ""  # Fallback if parsing fails  
      
    return sql_query  
  
def execute_sql_query(sql_query):  
    print(f"Executing SQL Query: {sql_query}")  # Add this line for debugging  
    adjusted_sql_query = sql_query.replace("CURRENT_DATE", "CAST(GETDATE() AS DATE)")  
      
    g.cursor.execute(adjusted_sql_query)  
    columns = [column[0] for column in g.cursor.description]  
    results = [dict(zip(columns, row)) for row in g.cursor.fetchall()]  
    return results  
  
@app.route('/', methods=['GET', 'POST'])  
def home():  
    if request.method == 'POST':  
        nlp_query = request.form.get('nlp_query', '')  
        if nlp_query:  
            sql_query = nlp_to_sql(nlp_query)  
            if sql_query:  
                try:  
                    results = execute_sql_query(sql_query)  
                    return render_template('index.html', results=json.dumps(results, indent=4), nlp_query=nlp_query, sql_query=sql_query)  
                except Exception as e:  
                    return render_template('index.html', error=f"Error executing your query: {str(e)}", nlp_query=nlp_query)  
            else:  
                return render_template('index.html', error="Failed to generate response, write it properly.", nlp_query=nlp_query)  
        else:  
            return render_template('index.html', error="Please enter a query.")  
    return render_template('index.html')  
  
if __name__ == "__main__":  
    # Note: Use an environment variable or a different method to determine if you're in a production environment and adjust accordingly.  
    # For example, you might want to set debug to False in production.  
    app.run(debug=False)  

