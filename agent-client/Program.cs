using Azure;
using Azure.AI.OpenAI;
using Azure.Core;
using Azure.Identity;
using DotNetEnv;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;

Env.TraversePath().Load();

var endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")
    ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT is not set.");
var deployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT_NAME") ?? "gpt-4o-mini";
var apiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY");
var mcpUrl = Environment.GetEnvironmentVariable("MCP_SERVER_URL") ?? "http://mcp-server:8000/mcp";

// --- 1. Wait for the MCP service to be reachable (compose healthcheck backstop) ---
await WaitForEndpointAsync(mcpUrl, TimeSpan.FromSeconds(30));

// --- 2. Connect to MCP over SSE ---
Console.WriteLine($"🔌 Connecting to MCP: {mcpUrl}");
var mcpTransport = new SseClientTransport(new SseClientTransportOptions
{
    Endpoint = new Uri(mcpUrl),
    Name = "tasks-mcp",
});
await using var mcpClient = await McpClientFactory.CreateAsync(mcpTransport);

var mcpTools = await mcpClient.ListToolsAsync();
Console.WriteLine($"🧰 MCP tools discovered: {string.Join(", ", mcpTools.Select(t => t.Name))}");

// --- 3. Build Azure OpenAI chat client ---
var openAiClient = !string.IsNullOrWhiteSpace(apiKey)
    ? new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
    : new AzureOpenAIClient(new Uri(endpoint), ResolveCredential());

AIAgent agent = openAiClient
    .GetChatClient(deployment)
    .AsIChatClient()
    .CreateAIAgent(
        name: "TaskAgent",
        instructions:
            "Sos un asistente que gestiona una lista de tareas. " +
            "Usás exclusivamente las herramientas MCP disponibles (list_tasks, add_task, complete_task, stats) " +
            "para consultar o modificar el estado. No inventes tareas: siempre llamá a las tools. " +
            "Respondé en español, con claridad y al grano.",
        tools: [.. mcpTools.Cast<AITool>()]);

// --- 4. Run ---
var prompt = args.Length > 0
    ? string.Join(' ', args)
    : "Mostrame el estado actual de tareas, agregá una tarea nueva de alta prioridad llamada 'Publicar sample Docker + MCP', y devolveme las estadísticas finales.";

Console.WriteLine($"\n> Prompt: {prompt}\n");
Console.WriteLine("--- Respuesta (streaming) ---");
await foreach (var update in agent.RunStreamingAsync(prompt))
{
    Console.Write(update);
}
Console.WriteLine("\n------------------------------");

// ----------------- helpers -----------------

static TokenCredential ResolveCredential() =>
    new ChainedTokenCredential(
        new AzureCliCredential(),
        new DefaultAzureCredential(includeInteractiveCredentials: false));

static async Task WaitForEndpointAsync(string url, TimeSpan timeout)
{
    var uri = new Uri(url);
    var baseUri = new Uri($"{uri.Scheme}://{uri.Host}:{uri.Port}");
    using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
    var deadline = DateTime.UtcNow + timeout;
    var attempt = 0;
    while (DateTime.UtcNow < deadline)
    {
        attempt++;
        try
        {
            using var resp = await http.GetAsync(baseUri);
            Console.WriteLine($"✅ MCP host reachable at {baseUri} (attempt {attempt})");
            return;
        }
        catch
        {
            await Task.Delay(TimeSpan.FromSeconds(1));
        }
    }
    throw new InvalidOperationException($"MCP host {baseUri} unreachable after {timeout.TotalSeconds:0}s");
}
