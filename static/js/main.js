// static/js/main.js
async function pollDue() {
  try {
    const res = await fetch('/api/due', { credentials: 'same-origin' });
    if (!res.ok) return;
    const ct = res.headers.get('Content-Type') || '';
    if (!ct.includes('application/json')) return;
    const items = await res.json();
    if (items && items.length) {
      items.forEach(i => {
        if (Notification && Notification.permission === 'granted') {
          new Notification('Medicine reminder: ' + i.medicine_name, { body: 'Dosage: ' + (i.dosage || '') + ' Time: ' + i.reminder_time });
        } else {
          console.log('Reminder:', i.medicine_name);
        }
      });
    }
  } catch (e) {
    console.error('pollDue error', e);
  }
}

if ('Notification' in window) {
  if (Notification.permission === 'default') {
    Notification.requestPermission().catch(err => console.warn('Notification permission request failed', err));
  }
  setInterval(pollDue, 30000);
  pollDue();
}
