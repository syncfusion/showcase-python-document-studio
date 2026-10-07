using Syncfusion.Presentation;
using Syncfusion.PresentationRenderer;

namespace EShare.Documents;

public static partial class DocumentService
{
    public static void MarkPowerPoint(string input, string output, string label)
    {
        ValidatePaths(input, output);
        ValidateLabel(label);
        using var stream = File.OpenRead(input);
        using var deck = Presentation.Open(stream);
        foreach (ISlide slide in deck.Slides)
        {
            // Remove only this sample's named markings, permitting reclassification.
            for (int i = slide.Shapes.Count - 1; i >= 0; i--)
                if (slide.Shapes[i].ShapeName is "eSHARE.Classification.Header" or "eSHARE.Classification.Footer")
                    slide.Shapes.RemoveAt(i);
            AddMark(slide, label, 8, "Header");
            AddMark(slide, label, slide.SlideSize.Height - 26, "Footer");
        }
        using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
        deck.Save(result);
    }

    private static void AddMark(ISlide slide, string label, double top, string position)
    {
        var shape = slide.Shapes.AddTextBox(18, top, slide.SlideSize.Width - 36, 18);
        shape.ShapeName = "eSHARE.Classification." + position;
        var paragraph = shape.TextBody.AddParagraph(label);
        paragraph.HorizontalAlignment = HorizontalAlignmentType.Center;
        paragraph.Font.FontName = "Liberation Sans";
        paragraph.Font.FontSize = 9;
        paragraph.Font.Bold = true;
    }

    public static void PowerPointToPdf(string input, string output)
    {
        ValidatePaths(input, output);
        using var stream = File.OpenRead(input);
        using var deck = Presentation.Open(stream);
        using var fonts = LinuxFontFallback.Attach(deck);
        using var pdf = PresentationToPdfConverter.Convert(deck);
        using var result = new FileStream(output, FileMode.Create, FileAccess.Write);
        pdf.Save(result);
    }
}
