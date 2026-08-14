namespace ICTMasterSuite.Tests;

using FluentAssertions;
using ICTMasterSuite.Core.Models;
using ICTMasterSuite.Core.Services;
using Xunit;

public class ConfigServiceTests
{
    [Fact]
    public void LoadConfig_ShouldReturnDefaultConfig_WhenFileDoesNotExist()
    {
        // Arrange
        var tempFile = Path.Combine(Path.GetTempPath(), $"test_config_{Guid.NewGuid()}.json");
        var service = new ConfigService(customPath: tempFile);

        try
        {
            // Act
            var config = service.Config;

            // Assert
            config.Should().NotBeNull();
            config.CaminhoLogsTri.Should().Be("//147.1.0.95/teste_ict/ict02/defeitos_tri");
            config.CaminhoLogsAgilent.Should().Be("//147.1.0.95/teste_ict/ict01/defeitos");
            config.CaminhoCopiaOrigem.Should().Be("//147.1.0.95/teste_ict/ict02");
            config.CaminhoCopiaDestino.Should().Be("//147.1.0.95/teste_ict/ict02/defeitos_tri");
            config.CaminhoBancoRede.Should().Be("//147.1.0.95/teste_ict/banco_dados_falhas.db");
            config.AutoStartWindows.Should().BeFalse();
            config.KeepInTray.Should().BeFalse();
            config.AutoCopiaTriDefeitos.Should().BeTrue();
        }
        finally
        {
            if (File.Exists(tempFile))
            {
                File.Delete(tempFile);
            }
        }
    }

    [Fact]
    public void SaveConfig_ShouldPersistNewValuesAndReturnUpdatedRecord()
    {
        // Arrange
        var tempFile = Path.Combine(Path.GetTempPath(), $"test_config_{Guid.NewGuid()}.json");
        var service = new ConfigService(customPath: tempFile);

        try
        {
            var newConfig = service.Config with
            {
                CaminhoLogsTri = "C:\\Custom\\Logs\\Tri",
                AutoStartWindows = true
            };

            // Act
            service.SaveConfig(newConfig);
            var reloadedService = new ConfigService(customPath: tempFile);

            // Assert
            reloadedService.Config.CaminhoLogsTri.Should().Be("C:\\Custom\\Logs\\Tri");
            reloadedService.Config.AutoStartWindows.Should().BeTrue();
        }
        finally
        {
            if (File.Exists(tempFile))
            {
                File.Delete(tempFile);
            }
        }
    }

    [Fact]
    public void DomainRecords_ShouldBeImmutableAndConstructCorrectly()
    {
        // Arrange & Act
        var meta = new LogMetadata("TRI", "12/08/2026 10:00:00", "6783001TDB", "MODEL1", "FAIL", "red");
        var diag = new Diagnostico("FAIL", new[] { "PC1100" }, new[] { "A1" }, Array.Empty<string>(), Array.Empty<string>(), Array.Empty<string>(), 1);

        // Assert
        meta.Tipo.Should().Be("TRI");
        meta.Status.Should().Be("FAIL");
        diag.TotalErros.Should().Be(1);
        diag.Componentes.Should().ContainSingle().Which.Should().Be("PC1100");
    }
}
