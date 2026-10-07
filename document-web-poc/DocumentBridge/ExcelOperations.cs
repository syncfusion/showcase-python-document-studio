using Syncfusion.XlsIO;
using Syncfusion.XlsIORenderer;

namespace EShare.Documents;

public static partial class DocumentService
{
    /// <summary>Reserves center header/footer slots; preserves left/right slots and cells.</summary>
    public static void MarkExcel(string input, string output, string label)
    {
        ValidatePaths(input, output);
        ValidateLabel(label);
        // Excel interprets ampersands as formatting commands.
        string literal = label.Replace("&", "&&");
        using var engine = new ExcelEngine();
        engine.Excel.DefaultVersion = ExcelVersion.Xlsx;
        using var stream = File.OpenRead(input);
        var book = engine.Excel.Workbooks.Open(stream);
        try
        {
            foreach (IWorksheet sheet in book.Worksheets)
            {
                var setup = sheet.PageSetup;
                setup.CenterHeader = literal;
                setup.CenterFooter = literal;
                setup.FirstPage.CenterHeader = literal;
                setup.FirstPage.CenterFooter = literal;
                setup.EvenPage.CenterHeader = literal;
                setup.EvenPage.CenterFooter = literal;
            }
            using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
            book.SaveAs(result);
        }
        finally { book.Close(); }
    }

    public static void ExcelToPdf(string input, string output)
    {
        ValidatePaths(input, output);
        using var engine = new ExcelEngine();
        using var stream = File.OpenRead(input);
        var book = engine.Excel.Workbooks.Open(stream);
        try
        {
            using var fonts = LinuxFontFallback.Attach(engine.Excel);
            using var renderer = new XlsIORenderer();
            // Preserve source print settings; do not force a wide sheet onto one page.
            using var pdf = renderer.ConvertToPDF(book);
            using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
            pdf.Save(result);
        }
        finally { book.Close(); }
    }
}
