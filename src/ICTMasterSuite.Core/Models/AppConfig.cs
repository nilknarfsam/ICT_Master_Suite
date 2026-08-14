namespace ICTMasterSuite.Core.Models;

using System.Text.Json.Serialization;

public record AppConfig(
    [property: JsonPropertyName("caminho_logs_tri")] string CaminhoLogsTri = "//147.1.0.95/teste_ict/ict02/defeitos_tri",
    [property: JsonPropertyName("caminho_logs_agilent")] string CaminhoLogsAgilent = "//147.1.0.95/teste_ict/ict01/defeitos",
    [property: JsonPropertyName("caminho_copia_origem")] string CaminhoCopiaOrigem = "//147.1.0.95/teste_ict/ict02",
    [property: JsonPropertyName("caminho_copia_destino")] string CaminhoCopiaDestino = "//147.1.0.95/teste_ict/ict02/defeitos_tri",
    [property: JsonPropertyName("caminho_banco_rede")] string CaminhoBancoRede = "//147.1.0.95/teste_ict/banco_dados_falhas.db",
    [property: JsonPropertyName("auto_start_windows")] bool AutoStartWindows = false,
    [property: JsonPropertyName("keep_in_tray")] bool KeepInTray = false,
    [property: JsonPropertyName("auto_copia_tri_defeitos")] bool AutoCopiaTriDefeitos = true
);
