// Minimal client. No tokens. No empty params. Just works.
(() => {
    const $ = (id) => document.getElementById(id);
  
    const state = { page: 1, pageSize: 12 };
  
    // Admin-lite: add / seed
    $('seedBtn').onclick = async () => {
      await fetch('/api/v1/items/seed_demo', { method: 'POST' });
      await list();
    };
  
    $('addBtn').onclick = async () => {
      const body = {
        name: $('addName').value.trim(),
        category: $('addCategory').value,
        device: $('addDevice').value,
        voice_prompt: $('addPrompt').value.trim() || null,
        description: $('addDesc').value.trim() || null,
        price: 0
      };
      if (!body.name) return alert('Title is required');
      const res = await fetch('/api/v1/items', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      if (!res.ok) return alert('Create failed');
      $('addName').value = $('addPrompt').value = $('addDesc').value = '';
      await list();
    };
  
    // Browse
    $('searchBtn').onclick = () => { state.page = 1; list(); };
    $('resetBtn').onclick  = () => {
      $('q').value = ''; $('qCategory').value = ''; $('qDevice').value = '';
      state.page = 1; list();
    };
  
    async function list() {
      const sp = new URLSearchParams();
      if ($('q').value.trim()) sp.set('q', $('q').value.trim());
      if ($('qCategory').value) sp.set('category', $('qCategory').value);
      if ($('qDevice').value)   sp.set('device', $('qDevice').value);
      sp.set('page', state.page); sp.set('page_size', state.pageSize);
  
      const res = await fetch('/api/v1/items?' + sp.toString());
      if (!res.ok) return console.error('List failed');
      const items = await res.json();
      $('count').textContent = `(${items.length} shown)`;
      renderGrid(items);
    }
  
    function renderGrid(items) {
      const grid = $('grid');
      grid.innerHTML = '';
      if (!items.length) {
        grid.innerHTML = `<div class="text-sm text-gray-500">No items. Click “Seed demo”.</div>`;
        return;
      }
      for (const it of items) {
        const el = document.createElement('div');
        el.className = 'rounded-xl border bg-white p-4 shadow-sm';
        el.innerHTML = `
          <div class="flex justify-between items-start">
            <div>
              <div class="font-medium">${esc(it.name)}</div>
              <div class="text-xs text-gray-500">${esc(it.category)} • ${esc(it.device)}</div>
            </div>
          </div>
          <div class="mt-2 text-sm text-gray-700">${esc(it.description || '')}</div>
          <div class="mt-2 text-xs text-gray-500">Voice prompt: “${esc(it.voice_prompt || '—')}”</div>
          <div class="mt-3">
            <button class="del rounded-md bg-red-600 px-3 py-1.5 text-white text-sm hover:bg-red-700" data-id="${it.id}">Delete</button>
          </div>
        `;
        grid.appendChild(el);
      }
      grid.querySelectorAll('.del').forEach(btn => {
        btn.onclick = async () => {
          if (!confirm('Delete this item?')) return;
          await fetch('/api/v1/items/' + btn.dataset.id, { method: 'DELETE' });
          await list();
        };
      });
    }
  
    // Recommendations
    $('recBtn').onclick = async () => {
      const sp = new URLSearchParams();
      if ($('persona').value) sp.set('persona', $('persona').value);
      sp.set('goal', $('goal').value);
      sp.set('device', $('device').value);
      const res = await fetch('/api/v1/recommend?' + sp.toString());
      if (!res.ok) return alert('Recommend failed');
      const recs = await res.json();
      renderRecs(recs);
    };
  
    function renderRecs(items) {
      const grid = $('recGrid');
      grid.innerHTML = '';
      if (!items.length) {
        grid.innerHTML = `<div class="text-sm text-gray-500">No matches — add or seed skills first.</div>`;
        return;
      }
      for (const it of items) {
        const el = document.createElement('div');
        el.className = 'rounded-xl border bg-white p-4 shadow-sm';
        el.innerHTML = `
          <div class="font-medium">${esc(it.name)}</div>
          <div class="text-xs text-gray-500">${esc(it.category)} • ${esc(it.device)}</div>
          <div class="mt-2 text-sm text-gray-700">${esc(it.description || '')}</div>
          <div class="mt-2 text-xs text-gray-500">Assistant will say: “${esc(it.voice_prompt || '—')}”</div>
        `;
        grid.appendChild(el);
      }
    }
  
    const esc = (s) => String(s || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    list();
  })();
  