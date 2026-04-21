# syntax=docker/dockerfile:1.7

FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src

COPY agent-client/AgentClient.csproj ./agent-client/
RUN dotnet restore ./agent-client/AgentClient.csproj

COPY agent-client/ ./agent-client/
RUN dotnet publish ./agent-client/AgentClient.csproj \
    -c Release \
    -o /app/publish \
    --no-restore \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/runtime:8.0-alpine AS runtime
RUN addgroup -S agent && adduser -S agent -G agent
WORKDIR /app

COPY --from=build --chown=agent:agent /app/publish .
USER agent

ENV DOTNET_RUNNING_IN_CONTAINER=true \
    DOTNET_EnableDiagnostics=0

ENTRYPOINT ["dotnet", "AgentClient.dll"]
