using System.Text.Json;
using EShare.Documents;

try
{
    // Read one request from the parent Python process. Never read document bytes over a network.
    var request = JsonSerializer.Deserialize<WorkerRequest>(Console.In.ReadToEnd())
        ?? throw new ArgumentException("A JSON request is required.");
    var key = Environment.GetEnvironmentVariable("SYNCFUSION_LICENSE_KEY");
    if (!string.IsNullOrWhiteSpace(key)) DocumentService.RegisterLicense(key);
    else if (!request.AllowTrial) throw new InvalidOperationException("A Syncfusion license key is required.");
    ArgumentException.ThrowIfNullOrWhiteSpace(request.Input);
    ArgumentException.ThrowIfNullOrWhiteSpace(request.Output);
    switch (request.Operation)
    {
        case "MarkWord": DocumentService.MarkWord(request.Input, request.Output, request.Label!); break;
        case "MarkExcel": DocumentService.MarkExcel(request.Input, request.Output, request.Label!); break;
        case "MarkPowerPoint": DocumentService.MarkPowerPoint(request.Input, request.Output, request.Label!); break;
        case "WordToPdf": DocumentService.WordToPdf(request.Input, request.Output); break;
        case "ExcelToPdf": DocumentService.ExcelToPdf(request.Input, request.Output); break;
        case "PowerPointToPdf": DocumentService.PowerPointToPdf(request.Input, request.Output); break;
        case "WatermarkPdf": DocumentService.WatermarkPdf(request.Input, request.Output, request.Label!); break;
        default: throw new ArgumentException("Unknown operation.");
    }
    return 0;
}
catch (Exception error)
{
    // Full stack trace for diagnostics
    Console.Error.WriteLine($"{error.GetType().Name}: {error.Message}{Environment.NewLine}{error.StackTrace}");
    return 1;
}

internal sealed record WorkerRequest(string Operation, string Input, string Output, string? Label, bool AllowTrial);
