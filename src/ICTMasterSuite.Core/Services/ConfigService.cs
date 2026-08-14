namespace ICTMasterSuite.Core.Services;

using System.Text.Json;
using ICTMasterSuite.Core.Abstractions;
using ICTMasterSuite.Core.Models;

public class ConfigService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    private readonly IFileSystem _fileSystem;
    private readonly string _configFilePath;
    private readonly object _lock = new();
    private AppConfig _currentConfig;

    public ConfigService(IFileSystem? fileSystem = null, string? customPath = null)
    {
        _fileSystem = fileSystem ?? new PhysicalFileSystem();
        _configFilePath = customPath ?? Path.Combine(AppContext.BaseDirectory, "ict_config.json");
        _currentConfig = LoadConfigInternal();
    }

    public AppConfig Config
    {
        get
        {
            lock (_lock)
            {
                return _currentConfig;
            }
        }
    }

    public AppConfig LoadConfig()
    {
        lock (_lock)
        {
            _currentConfig = LoadConfigInternal();
            return _currentConfig;
        }
    }

    public void SaveConfig(AppConfig config)
    {
        lock (_lock)
        {
            _currentConfig = config;
            try
            {
                var json = JsonSerializer.Serialize(config, JsonOptions);
                _fileSystem.WriteAllText(_configFilePath, json);
            }
            catch
            {
                // Fallback de erro de escrita preservando estado em memória
            }
        }
    }

    private AppConfig LoadConfigInternal()
    {
        if (!_fileSystem.FileExists(_configFilePath))
        {
            var defaultConfig = new AppConfig();
            try
            {
                var json = JsonSerializer.Serialize(defaultConfig, JsonOptions);
                _fileSystem.WriteAllText(_configFilePath, json);
            }
            catch
            {
                // Fallback silencioso de escrita inicial
            }
            return defaultConfig;
        }

        try
        {
            var content = _fileSystem.ReadAllText(_configFilePath);
            var loaded = JsonSerializer.Deserialize<AppConfig>(content, JsonOptions);
            return loaded ?? new AppConfig();
        }
        catch
        {
            return new AppConfig();
        }
    }
}
