using Syncfusion.Drawing;
using Syncfusion.Pdf;
using Syncfusion.Pdf.Graphics;
using Syncfusion.Pdf.Parsing;

namespace EShare.Documents;

public static partial class DocumentService
{
    public static void WatermarkPdf(string input, string output, string label)
    {
        ValidatePaths(input, output);
        ValidateLabel(label);
        using var stream = File.OpenRead(input);
        using var document = new PdfLoadedDocument(stream);
        foreach (PdfPageBase page in document.Pages)
        {
            var graphics = page.Graphics;
            var size = graphics.ClientSize;
            PdfFont font = new PdfStandardFont(PdfFontFamily.Helvetica, 28);
            float measured = font.MeasureString(label).Width;
            float fontSize = Math.Min(28, 28 * size.Width * 0.8f / Math.Max(1, measured));
            font = new PdfStandardFont(PdfFontFamily.Helvetica, fontSize);
            var state = graphics.Save();
            try
            {
                graphics.SetTransparency(0.25f);
                graphics.TranslateTransform(size.Width / 2, size.Height / 2);
                graphics.RotateTransform(-30);
                graphics.DrawString(label, font, PdfBrushes.Gray,
                    new RectangleF(-size.Width / 2, -30, size.Width, 60),
                    new PdfStringFormat(PdfTextAlignment.Center, PdfVerticalAlignment.Middle));
            }
            finally { graphics.Restore(state); }
        }
        using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
        document.Save(result);
    }
}
