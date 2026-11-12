(function () {
  const modal = document.querySelector('[data-query-action-modal]');
  if (!(modal instanceof HTMLElement)) {
    return;
  }

  const titleNode = modal.querySelector('[data-query-action-modal-title]');
  const messageNode = modal.querySelector('[data-query-action-modal-message]');
  const inputNode = modal.querySelector('[data-query-action-modal-input]');
  const errorNode = modal.querySelector('[data-query-action-modal-error]');
  const submitButton = modal.querySelector('[data-query-action-modal-submit]');
  const cancelButton = modal.querySelector('[data-query-action-modal-cancel]');
  let activeTrigger = null;

  const actionConfig = {
    answer: {
      title: 'Answer Query',
      message: 'Enter the answer to send for this query.',
      placeholder: 'Answer',
      required: true,
    },
    request_clarification: {
      title: 'Request Clarification',
      message: 'Enter the clarification request to send this query back to the site.',
      placeholder: 'Clarification request',
      required: true,
    },
    resolve: {
      title: 'Resolve Query',
      message: 'Enter the resolution note for this query.',
      placeholder: 'Resolution note',
      required: true,
    },
    close: {
      title: 'Close Query',
      message: 'Close this resolved query. A closing note is optional.',
      placeholder: 'Closing note',
      required: false,
    },
    reopen: {
      title: 'Reopen Query',
      message: 'Enter the reason for reopening this query.',
      placeholder: 'Reopen reason',
      required: true,
    },
    reopen_validation_issue: {
      title: 'Reopen Validation Issue',
      message: 'Enter the reason for reopening this validation issue.',
      placeholder: 'Reopen reason',
      required: true,
    },
    cancel: {
      title: 'Cancel Query',
      message: 'Enter the reason for cancelling this query.',
      placeholder: 'Cancellation reason',
      required: true,
    },
  };

  function setError(message) {
    if (!(errorNode instanceof HTMLElement)) {
      return;
    }
    errorNode.textContent = message || '';
    errorNode.hidden = !message;
  }

  function openModal(trigger) {
    const action = String(trigger.dataset.queryAction || '').trim().toLowerCase();
    const config = actionConfig[action];
    if (!config) {
      return;
    }
    activeTrigger = trigger;
    if (titleNode instanceof HTMLElement) {
      const label = String(trigger.dataset.queryLabel || '').trim();
      titleNode.textContent = label ? `${config.title} ${label}` : config.title;
    }
    if (messageNode instanceof HTMLElement) {
      messageNode.textContent = config.message;
    }
    if (inputNode instanceof HTMLTextAreaElement) {
      inputNode.value = '';
      inputNode.placeholder = config.placeholder;
    }
    setError('');
    modal.hidden = false;
    if (inputNode instanceof HTMLTextAreaElement) {
      inputNode.focus();
    }
  }

  function closeModal() {
    modal.hidden = true;
    activeTrigger = null;
    setError('');
  }

  function parseResponse(response) {
    return response.text().then(function (text) {
      let data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (_) {
          data = {};
        }
      }
      return { ok: response.ok, status: response.status, data: data };
    });
  }

  function errorMessage(result) {
    const errors = result && result.data && result.data.error;
    if (Array.isArray(errors) && errors.length > 0) {
      return errors.join(', ');
    }
    if (result && result.status === 403) {
      return 'Permission denied.';
    }
    return 'Request failed.';
  }

  function submitAction() {
    if (!(activeTrigger instanceof HTMLElement)) {
      return;
    }
    const action = String(activeTrigger.dataset.queryAction || '').trim().toLowerCase();
    const config = actionConfig[action];
    const actionUrl = String(activeTrigger.dataset.queryActionUrl || '').trim();
    const messageText = inputNode instanceof HTMLTextAreaElement ? String(inputNode.value || '').trim() : '';
    if (!config || !actionUrl) {
      setError('Action is not available.');
      return;
    }
    if (config.required && !messageText) {
      setError('Message is required.');
      if (inputNode instanceof HTMLTextAreaElement) {
        inputNode.focus();
      }
      return;
    }
    setError('');
    if (submitButton instanceof HTMLButtonElement) {
      submitButton.disabled = true;
    }
    window
      .fetch(actionUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_text: messageText }),
      })
      .then(parseResponse)
      .then(function (result) {
        if (!result.ok || !result.data || result.data.ok !== true) {
          setError(errorMessage(result));
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        setError('Network error.');
      })
      .finally(function () {
        if (submitButton instanceof HTMLButtonElement) {
          submitButton.disabled = false;
        }
      });
  }

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('[data-query-action-trigger]');
    if (trigger instanceof HTMLElement) {
      event.preventDefault();
      openModal(trigger);
    }
  });

  if (cancelButton instanceof HTMLElement) {
    cancelButton.addEventListener('click', closeModal);
  }
  if (submitButton instanceof HTMLElement) {
    submitButton.addEventListener('click', submitAction);
  }
})();
