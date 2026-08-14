namespace ICTMasterSuite.Core.Models;

public record LogHit(
    string NomeArquivo,
    string CaminhoCompleto,
    DateTime DataModificacao,
    long TamanhoBytes
);
