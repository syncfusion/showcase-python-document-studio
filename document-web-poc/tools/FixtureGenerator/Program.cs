using Syncfusion.DocIO;
using Syncfusion.DocIO.DLS;
using Syncfusion.XlsIO;
using Syncfusion.Presentation;
var root = Path.GetFullPath(args[0]);
Directory.CreateDirectory(root);
var key = Environment.GetEnvironmentVariable("SYNCFUSION_LICENSE_KEY");
if (!string.IsNullOrWhiteSpace(key)) EShare.Documents.DocumentService.RegisterLicense(key);
using (var document = new WordDocument())
{
    document.AddSection().AddParagraph().AppendText("Web POC sample document.");
    document.Save(Path.Combine(root, "input.docx"), Syncfusion.DocIO.FormatType.Docx);
}
using (var engine = new ExcelEngine())
{
    engine.Excel.DefaultVersion = ExcelVersion.Xlsx;
    var book = engine.Excel.Workbooks.Create(1);
    book.Worksheets[0].Range["A1"].Text = "Web POC sample workbook";
    book.SaveAs(Path.Combine(root, "input.xlsx"));
    book.Close();
}
using (var deck = Presentation.Create())
{
    deck.Slides.Add(SlideLayoutType.Blank).Shapes.AddTextBox(40,100,400,100)
        .TextBody.AddParagraph("Web POC sample presentation");
    deck.Save(Path.Combine(root, "input.pptx"));
}
Console.WriteLine("Created synthetic DOCX, XLSX and PPTX samples.");
