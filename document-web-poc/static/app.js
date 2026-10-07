var form = document.querySelector('#document-form');
var fileHost = document.querySelector('#file');
var labelHost = document.querySelector('#label');
var statusLine = document.querySelector('#status');
var download = document.querySelector('#download');
var themeToggle = document.querySelector('#theme-toggle');
var themeLink = document.getElementById('ej2-theme');
var resultUrl;
var busy = false;
var uploader;
var operationList;
var labelBox;
var submitButton;
var downloadButton;

var operations = [
  { text: 'Classify Word document', value: 'mark-word', extension: '.docx', needsLabel: true },
  { text: 'Classify Excel workbook', value: 'mark-excel', extension: '.xlsx', needsLabel: true },
  { text: 'Classify PowerPoint slides', value: 'mark-ppt', extension: '.pptx', needsLabel: true },
  { text: 'Word to PDF', value: 'word-to-pdf', extension: '.docx', needsLabel: false },
  { text: 'Excel to PDF', value: 'excel-to-pdf', extension: '.xlsx', needsLabel: false },
  { text: 'PowerPoint to PDF', value: 'ppt-to-pdf', extension: '.pptx', needsLabel: false },
  { text: 'Watermark PDF', value: 'watermark-pdf', extension: '.pdf', needsLabel: true }
];
var hints = {
  'mark-word': 'Adds the label to Word headers and footers.',
  'mark-excel': 'Adds the label to Excel print headers and footers. View it in Print Preview.',
  'mark-ppt': 'Adds the label at the top and bottom of every slide.',
  'word-to-pdf': 'Converts the Word document into a PDF.',
  'excel-to-pdf': 'Converts the workbook using its print settings.',
  'ppt-to-pdf': 'Converts the presentation into a PDF.',
  'watermark-pdf': 'Adds a translucent diagonal watermark to every PDF page.'
};

function endsWith(value, suffix) {
  return value.length >= suffix.length && value.substring(value.length - suffix.length) === suffix;
}

function fileExtension(name) {
  var dot = name.lastIndexOf('.');
  return dot >= 0 ? name.substring(dot).toLowerCase() : '';
}

function selectedOperation() {
  return operationList.getDataByValue(operationList.value);
}

function clearResult() {
  if (resultUrl) URL.revokeObjectURL(resultUrl);
  resultUrl = undefined;
  download.hidden = true;
  download.removeAttribute('href');
  download.removeAttribute('download');
  if (downloadButton) downloadButton.content = 'Download result';
  statusLine.hidden = true;
}

function updateOperation() {
  var selected = selectedOperation();
  var needsLabel = !!(selected && selected.needsLabel);
  document.querySelector('#label-field').hidden = !needsLabel;
  if (needsLabel) labelBox.addAttributes({ required: 'required' });
  else labelBox.removeAttributes(['required']);
  if (!busy) labelBox.enabled = needsLabel;
  document.querySelector('#operation-help').textContent = selected && hints[selected.value] ? hints[selected.value] : '';
}

function showStatus(message, error) {
  statusLine.textContent = message;
  statusLine.classList.toggle('error', !!error);
  statusLine.hidden = false;
}

function setBusy(isBusy) {
  busy = isBusy;
  uploader.enabled = !isBusy;
  operationList.enabled = !isBusy;
  submitButton.disabled = isBusy;
  submitButton.content = isBusy ? 'Processing…' : 'Process document →';
  if (isBusy) {
    labelBox.enabled = false;
    form.setAttribute('aria-busy', 'true');
  } else {
    form.removeAttribute('aria-busy');
    updateOperation();
  }
}

function onFileSelected(args) {
  clearResult();
  if (args.filesData && args.filesData.length > 1) args.filesData.splice(1);
  var file = args.filesData && args.filesData[0];
  if (!file || !file.name) return;
  var extension = fileExtension(file.name);
  var current = selectedOperation();
  if (!current || current.extension !== extension) {
    var match = null;
    var i;
    for (i = 0; i < operations.length; i++) {
      if (operations[i].extension === extension) {
        match = operations[i];
        break;
      }
    }
    if (match) operationList.value = match.value;
  }
  updateOperation();
}

if (window.__SYNCFUSION_JS_LICENSE_KEY__ && window.ej && ej.base && ej.base.registerLicense) {
  ej.base.registerLicense(window.__SYNCFUSION_JS_LICENSE_KEY__);
}

submitButton = new ej.buttons.Button({
  isPrimary: true,
  content: 'Process document →'
});
submitButton.appendTo('#submit');

downloadButton = new ej.buttons.Button({
  isPrimary: true,
  content: 'Download result'
});
downloadButton.appendTo('#download');

labelBox = new ej.inputs.TextBox({
  value: 'CONFIDENTIAL',
  width: '100%',
  floatLabelType: 'Never',
  htmlAttributes: {
    maxlength: '80',
    pattern: '[ -~]{1,80}',
    'aria-describedby': 'label-help'
  },
  input: clearResult
});
labelBox.appendTo(labelHost);

// Keep the input focused while a list item is pressed. Otherwise the popup
// closes on blur before mouseup and the choice is ignored.
document.addEventListener('mousedown', function (event) {
  var node = event.target;
  while (node && node !== document) {
    if (node.classList && node.classList.contains('e-list-item')) {
      event.preventDefault();
      return;
    }
    node = node.parentNode;
  }
}, true);

operationList = new ej.dropdowns.DropDownList({
  dataSource: operations,
  fields: { text: 'text', value: 'value' },
  value: 'mark-word',
  width: '100%',
  popupHeight: '320px',
  showClearButton: false,
  htmlAttributes: { 'aria-labelledby': 'operation-label' },
  change: function () {
    clearResult();
    updateOperation();
  }
});
operationList.appendTo('#operation');

uploader = new ej.inputs.Uploader({
  autoUpload: false,
  multiple: false,
  allowedExtensions: '.docx,.xlsx,.pptx,.pdf',
  minFileSize: 1,
  maxFileSize: 25 * 1024 * 1024,
  dropArea: document.querySelector('.upload'),
  showFileList: true,
  buttons: { browse: 'Select a file' },
  htmlAttributes: { 'aria-describedby': 'file-help' },
  selected: onFileSelected,
  removing: clearResult,
  clearing: clearResult
});
uploader.appendTo(fileHost);

form.addEventListener('submit', function (event) {
  event.preventDefault();
  clearResult();
  var files = uploader.getFilesData();
  var rawFile = files.length ? files[0].rawFile : null;
  var selected = selectedOperation();
  var expected = selected ? selected.extension : '';
  if (!rawFile || !expected || !endsWith((rawFile.name || '').toLowerCase(), expected)) {
    showStatus('Choose a ' + expected + ' file for this operation.', true);
    return;
  }
  if (rawFile.size > 25 * 1024 * 1024 || !rawFile.size) {
    showStatus('Choose a non-empty document smaller than 25 MB.', true);
    return;
  }
  var body = new FormData();
  body.append('file', rawFile, rawFile.name);
  body.append('operation', operationList.value);
  if (selected.needsLabel) body.append('label', labelBox.value);
  setBusy(true);
  showStatus('Processing your document. This may take a moment.');
  fetch('/api/process', { method: 'POST', body: body })
    .then(function (response) {
      if (!response.ok) {
        return response.json().catch(function () { return {}; }).then(function (error) {
          var detail = error && typeof error.detail === 'string' ? error.detail : 'Processing failed. Please try again.';
          throw new Error(detail);
        });
      }
      var disposition = response.headers.get('content-disposition') || '';
      var match = /filename="([^"]+)"/.exec(disposition);
      var filename = match ? match[1] : 'result';
      return response.blob().then(function (blob) {
        return { blob: blob, filename: filename };
      });
    })
    .then(function (result) {
      resultUrl = URL.createObjectURL(result.blob);
      download.href = resultUrl;
      download.setAttribute('download', result.filename);
      downloadButton.content = 'Download ' + result.filename;
      download.hidden = false;
      showStatus('Your document is ready. Temporary server files have been deleted.');
      download.focus();
    })
    .catch(function (error) {
      var message = error && error.message === 'Failed to fetch'
        ? 'Could not reach the server. Check your connection and try again.'
        : (error && error.message ? error.message : 'Processing failed. Please try again.');
      showStatus(message, true);
    })
    .then(function () {
      setBusy(false);
    });
});

function currentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'light';
}
function themeHref(theme) {
  return theme === 'dark'
    ? 'https://cdn.syncfusion.com/ej2/34.1.29/tailwind3-dark.css'
    : 'https://cdn.syncfusion.com/ej2/34.1.29/tailwind3.css';
}
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  if (themeLink) themeLink.href = themeHref(theme);
  themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
  localStorage.setItem('theme', theme);
}
themeToggle.addEventListener('click', function () {
  applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
});
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (event) {
  if (!localStorage.getItem('theme')) applyTheme(event.matches ? 'dark' : 'light');
});
themeToggle.setAttribute('aria-pressed', String(currentTheme() === 'dark'));

function parkLicenseBanner() {
  var nodes = document.body.children;
  var i;
  for (i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    if (!node.textContent || node.textContent.indexOf('trial version of Syncfusion') < 0) continue;
    node.style.position = 'static';
    node.style.zIndex = 'auto';
    node.style.top = 'auto';
    node.style.left = 'auto';
    node.style.right = 'auto';
    var main = document.querySelector('main');
    if (main && node !== main) document.body.insertBefore(node, main);
    return true;
  }
  return false;
}
if (!parkLicenseBanner()) {
  var licenseObserver = new MutationObserver(function () {
    if (parkLicenseBanner()) licenseObserver.disconnect();
  });
  licenseObserver.observe(document.body, { childList: true });
}

updateOperation();
