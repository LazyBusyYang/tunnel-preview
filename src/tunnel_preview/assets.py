from __future__ import annotations

COPY_JS = """\
function copyBlock(button) {
  const block = button.closest('.copy-block');
  const pre = block ? block.querySelector('pre') : null;
  if (!pre) return;

  let text;
  const code = pre.querySelector('code');
  if (code) {
    text = code.textContent;
  } else {
    text = Array.from(pre.querySelectorAll('.line')).map((line) => {
      const clone = line.cloneNode(true);
      const number = clone.querySelector('.num');
      if (number) number.remove();
      return clone.textContent;
    }).join('\\n');
  }

  const done = () => {
    const previous = button.textContent;
    button.textContent = 'Copied';
    setTimeout(() => {
      button.textContent = previous;
    }, 1200);
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
  done();
}

document.querySelectorAll('.copy-button').forEach((button) => {
  button.addEventListener('click', () => copyBlock(button));
});
"""
