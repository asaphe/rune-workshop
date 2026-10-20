using System;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// A WebView2 control, not an Edge browser window. No browser profile/sign-in UI.
internal sealed class RuneWindow : Form
{
    private readonly WebView2 view = new WebView2();
    private readonly Uri address;
    private readonly string dataFolder;
    private bool closingAllowed;
    private bool closePending;
    private bool ready;

    public RuneWindow(string url, string data, string icon)
    {
        address = new Uri(url);
        if (address.Scheme != "http" || address.Host != "127.0.0.1")
            throw new ArgumentException("Rune must use its local server.");
        dataFolder = Path.GetFullPath(data);
        Text = "Rune · Character Workshop";
        Icon = new Icon(icon);
        Size = new Size(1280, 900);
        MinimumSize = new Size(720, 500);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(21, 19, 12);
        view.Dock = DockStyle.Fill;
        Controls.Add(view);
        Shown += async delegate { await Initialize(); };
        FormClosing += OnClosingRequested;
        FormClosed += delegate { view.Dispose(); };
    }

    private bool Local(string value)
    {
        Uri target;
        return Uri.TryCreate(value, UriKind.Absolute, out target) &&
               target.Scheme == address.Scheme && target.Host == address.Host &&
               target.Port == address.Port;
    }

    private async Task Initialize()
    {
        try
        {
            var environment = await CoreWebView2Environment.CreateAsync(null, dataFolder);
            await view.EnsureCoreWebView2Async(environment);
            var core = view.CoreWebView2;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.IsStatusBarEnabled = false;
            core.Settings.IsGeneralAutofillEnabled = false;
            core.Settings.IsPasswordAutosaveEnabled = false;
            core.Settings.IsBuiltInErrorPageEnabled = false;
            core.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e)
            { if (!Local(e.Uri)) e.Cancel = true; };
            core.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e)
            { e.Handled = true; };
            core.PermissionRequested += delegate(object sender, CoreWebView2PermissionRequestedEventArgs e)
            { e.State = CoreWebView2PermissionState.Deny; };
            core.ProcessFailed += delegate(object sender, CoreWebView2ProcessFailedEventArgs e)
            {
                if (e.ProcessFailedKind == CoreWebView2ProcessFailedKind.BrowserProcessExited)
                    Fail("Rune's WebView2 runtime exited unexpectedly.");
            };
            core.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
            {
                if (!e.IsSuccess) Fail("Rune could not load its local server: " + e.WebErrorStatus);
                else ready = true;
            };
            core.Navigate(address.AbsoluteUri);
            // Python requests a graceful close only after its HTTP server drains writes.
            await Task.Run(delegate {
                try {
                    while (true) {
                        string command = Console.ReadLine();
                        if (command == null || command == "close") {
                            if (!IsDisposed) BeginInvoke((Action)delegate {
                                closingAllowed = true; Close();
                            });
                            break;
                        }
                    }
                } catch (ObjectDisposedException) { }
            });
        }
        catch (Exception e) { Fail(e.Message); }
    }

    private void Fail(string message)
    {
        Console.Error.WriteLine(message);
        Environment.ExitCode = 1;
        MessageBox.Show(this, message, "Rune", MessageBoxButtons.OK, MessageBoxIcon.Error);
        closingAllowed = true;
        Close();
    }

    private async void OnClosingRequested(object sender, FormClosingEventArgs e)
    {
        if (closingAllowed || !ready) return;
        e.Cancel = true;
        if (closePending) return;
        closePending = true;
        try
        {
            string busy = await view.ExecuteScriptAsync("Boolean(typeof isBusy==='function' && isBusy())");
            if (busy == "true") {
                MessageBox.Show(this, "Please wait for the current operation to finish, then close Rune.",
                                "Rune", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }
            string dirty = await view.ExecuteScriptAsync(
                "Boolean((typeof dirty==='function' && dirty()) || (typeof worldDirty==='function' && worldDirty()))");
            if (dirty == "true" && MessageBox.Show(this, "Discard unsaved changes and close Rune?",
                    "Rune", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
            closingAllowed = true;
            Close();
        }
        catch (Exception) {
            if (MessageBox.Show(this, "Rune could not check for unsaved changes. Close anyway?",
                    "Rune", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes) {
                closingAllowed = true; Close();
            }
        }
        finally { closePending = false; }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try {
            if (args.Length == 1 && args[0] == "--check") {
                CoreWebView2Environment.GetAvailableBrowserVersionString();
                return 0;
            }
            if (args.Length != 3) return 2;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new RuneWindow(args[0], args[1], args[2]));
            return Environment.ExitCode;
        } catch (Exception e) {
            Console.Error.WriteLine(e.ToString());
            if (!(args.Length == 1 && args[0] == "--check"))
                MessageBox.Show(e.Message, "Rune", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
    }
}
