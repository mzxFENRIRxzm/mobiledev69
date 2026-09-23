(() => {
  function enhance() {
    document.querySelectorAll('input[type=password]').forEach(input => {
      if (input.dataset.passwordToggle) return;
      input.dataset.passwordToggle = 'true';
      const wrapper = document.createElement('div');
      wrapper.className = 'the-x-password-control';
      input.before(wrapper);
      wrapper.append(input);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'the-x-password-toggle';
      button.textContent = 'แสดง';
      button.setAttribute('aria-label', 'แสดงรหัสผ่าน');
      button.setAttribute('aria-controls', input.id);
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        button.textContent = show ? 'ซ่อน' : 'แสดง';
        button.setAttribute('aria-label', show ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน');
        button.setAttribute('aria-pressed', String(show));
      });
      wrapper.append(button);
    });
  }
  enhance();
  new MutationObserver(enhance).observe(document.body, { childList: true, subtree: true });
})();
