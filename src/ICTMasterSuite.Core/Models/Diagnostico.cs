namespace ICTMasterSuite.Core.Models;

public record Diagnostico(
    string Status,
    IReadOnlyList<string> Componentes,
    IReadOnlyList<string> Coordenadas,
    IReadOnlyList<string> Curtos,
    IReadOnlyList<string> PinosAbertos,
    IReadOnlyList<string> Secoes,
    int TotalErros
);
