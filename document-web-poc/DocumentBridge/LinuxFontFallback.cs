using Syncfusion.DocIO.DLS;
using Syncfusion.Drawing;
using Syncfusion.Presentation;
using Syncfusion.XlsIO;
using ExcelSubstituteFontEventArgs = Syncfusion.XlsIO.Implementation.SubstituteFontEventArgs;
using PresentationSubstituteFontEventArgs = Syncfusion.Presentation.SubstituteFontEventArgs;
using WordSubstituteFontEventArgs = Syncfusion.DocIO.DLS.SubstituteFontEventArgs;

namespace EShare.Documents;

/// <summary>
/// Syncfusion calls Skia for the paragraph font, then for Tahoma, before it raises
/// SubstituteFont. Both calls null-ref when fontconfig has no matching family.
/// startup-azure.sh installs the vendored Liberation TTFs and maps Tahoma and the
/// usual Office families onto them. This handler still supplies those TTF streams
/// once the event runs.
/// </summary>
static class LinuxFontFallback
{
    private static readonly string[] Directories =
    [
        "/usr/local/share/fonts/document-poc",
        "/home/document-poc-fonts",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts/liberation",
    ];

    private static string? _directory;

    public static IDisposable Attach(IPresentation presentation)
    {
        if (!OperatingSystem.IsLinux())
            return Empty.Instance;
        var held = new HeldStreams();
        void Handler(object sender, PresentationSubstituteFontEventArgs args)
        {
            args.AlternateFontName = "Liberation Sans";
            args.AlternateFontStream = held.Open(args.FontStyle);
        }
        presentation.FontSettings.SubstituteFont += Handler;
        return new Subscription(() => presentation.FontSettings.SubstituteFont -= Handler, held);
    }

    public static IDisposable Attach(WordDocument document)
    {
        if (!OperatingSystem.IsLinux())
            return Empty.Instance;
        var held = new HeldStreams();
        void Handler(object sender, WordSubstituteFontEventArgs args)
        {
            args.AlternateFontName = "Liberation Sans";
            args.AlternateFontStream = held.Open(args.FontStyle);
        }
        document.FontSettings.SubstituteFont += Handler;
        return new Subscription(() => document.FontSettings.SubstituteFont -= Handler, held);
    }

    public static IDisposable Attach(IApplication application)
    {
        if (!OperatingSystem.IsLinux())
            return Empty.Instance;
        var held = new HeldStreams();
        void Handler(object sender, ExcelSubstituteFontEventArgs args)
        {
            args.AlternateFontName = "Liberation Sans";
            args.AlternateFontStream = held.Open(args.FontStyle);
        }
        application.SubstituteFont += Handler;
        return new Subscription(() => application.SubstituteFont -= Handler, held);
    }

    private static string Resolve(FontStyle style)
    {
        bool bold = style.HasFlag(FontStyle.Bold);
        bool italic = style.HasFlag(FontStyle.Italic);
        string file = bold && italic ? "LiberationSans-BoldItalic.ttf"
            : bold ? "LiberationSans-Bold.ttf"
            : italic ? "LiberationSans-Italic.ttf"
            : "LiberationSans-Regular.ttf";
        _directory ??= Directories.FirstOrDefault(dir =>
            File.Exists(Path.Combine(dir, "LiberationSans-Regular.ttf")));
        if (_directory is null)
            throw new FileNotFoundException(
                "Liberation Sans was not found. startup-azure.sh must copy fonts/ into the fontconfig directory before PDF conversion.");
        string path = Path.Combine(_directory, file);
        if (!File.Exists(path))
            throw new FileNotFoundException("Liberation font file was not found.", path);
        return path;
    }

    private sealed class HeldStreams : IDisposable
    {
        private readonly List<FileStream> _streams = new();

        public FileStream Open(FontStyle style)
        {
            var stream = new FileStream(Resolve(style), FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            _streams.Add(stream);
            return stream;
        }

        public void Dispose()
        {
            foreach (FileStream stream in _streams)
                stream.Dispose();
            _streams.Clear();
        }
    }

    private sealed class Subscription : IDisposable
    {
        private Action? _unsubscribe;
        private HeldStreams? _streams;

        public Subscription(Action unsubscribe, HeldStreams streams)
        {
            _unsubscribe = unsubscribe;
            _streams = streams;
        }

        public void Dispose()
        {
            _unsubscribe?.Invoke();
            _unsubscribe = null;
            _streams?.Dispose();
            _streams = null;
        }
    }

    private sealed class Empty : IDisposable
    {
        public static readonly Empty Instance = new();
        public void Dispose() { }
    }
}
