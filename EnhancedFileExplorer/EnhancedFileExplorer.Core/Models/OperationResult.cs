namespace EnhancedFileExplorer.Core.Models;

/// <summary>
/// Result of a file operation.
/// </summary>
public class OperationResult
{
    public bool IsSuccess { get; private set; }
    public string? ErrorMessage { get; private set; }
    public Exception? Exception { get; private set; }
    public string? ResultPath { get; private set; }

    private OperationResult() { }

    public static OperationResult Success(string? resultPath = null)
    {
        return new OperationResult
        {
            IsSuccess = true,
            ResultPath = resultPath
        };
    }

    public static OperationResult Failure(string errorMessage, Exception? exception = null)
    {
        return new OperationResult
        {
            IsSuccess = false,
            ErrorMessage = errorMessage,
            Exception = exception
        };
    }
}

