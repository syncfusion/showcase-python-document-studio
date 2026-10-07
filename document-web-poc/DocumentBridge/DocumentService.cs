using Syncfusion.DocIO;
using Syncfusion.DocIO.DLS;
using Syncfusion.DocIORenderer;
using Syncfusion.Licensing;

namespace EShare.Documents;

/// <summary>Local-file proof of concept. One document instance per operation.</summary>
public static partial class DocumentService
{
    private const string MarkStyle = "eSHARE Classification";

    public static void RegisterLicense(string key)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(key);
        SyncfusionLicenseProvider.RegisterLicense(key);
    }

    private static void ValidatePaths(string input, string output)
    {
        if (!File.Exists(input)) throw new FileNotFoundException("Input document not found.", input);
        if (Path.GetFullPath(input) == Path.GetFullPath(output))
            throw new ArgumentException("Use a separate output file.");
        // if (File.Exists(output)) throw new IOException("Output already exists: " + output);
    }

    private static void ValidateLabel(string label)
    {
        if (string.IsNullOrWhiteSpace(label) || label.Length > 80 || label.Any(c => c < 32 || c > 126))
            throw new ArgumentException("This sample accepts 1–80 printable ASCII characters for the label.");
    }

    public static void MarkWord(string input, string output, string label)
    {
        ValidatePaths(input, output);
        ValidateLabel(label);
        using var stream = File.OpenRead(input);
        using var document = new WordDocument(stream, FormatType.Docx);
        if (document.Styles.FindByName(MarkStyle) is null)
        {
            var style = (WParagraphStyle)document.AddParagraphStyle(MarkStyle);
            style.CharacterFormat.FontName = "Liberation Sans";
            style.CharacterFormat.FontSize = 9;
            style.CharacterFormat.Bold = true;
            style.ParagraphFormat.HorizontalAlignment = HorizontalAlignment.Center;
        }
        for (int i = 0; i < document.Sections.Count; i++)
        {
            var hf = document.Sections[i].HeadersFooters;
            foreach (var body in new[] { hf.Header, hf.Footer, hf.FirstPageHeader,
                         hf.FirstPageFooter, hf.EvenHeader, hf.EvenFooter })
            {
                // Linked sections inherit the already-marked previous header/footer.
                if (i > 0 && body.LinkToPrevious) continue;
                WParagraph? owned = null;
                foreach (WParagraph p in body.Paragraphs)
                    if (p.StyleName == MarkStyle) { owned = p; break; }
                owned ??= (WParagraph)body.AddParagraph();
                owned.ApplyStyle(MarkStyle);
                owned.Text = label;
            }
        }
        using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
        document.Save(result, FormatType.Docx);
    }

    public static void WordToPdf(string input, string output)
    {
        ValidatePaths(input, output);
        using var stream = File.OpenRead(input);
        using var document = new WordDocument(stream, FormatType.Docx);
        using var fonts = LinuxFontFallback.Attach(document);
        using var renderer = new DocIORenderer();
        using var pdf = renderer.ConvertToPDF(document);
        using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
        pdf.Save(result);
    }
}
