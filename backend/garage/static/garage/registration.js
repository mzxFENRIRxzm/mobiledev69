(() => {
  const type = document.getElementById('id_account_type');
  const fields = document.getElementById('shop-fields');
  const lat = document.getElementById('id_latitude');
  const lng = document.getElementById('id_longitude');
  const status = document.getElementById('map-status');
  const address = document.getElementById('id_shop_address');
  const addressStatus = document.getElementById('address-status');
  const refill = document.getElementById('address-from-pin');
  let lookupTimer, lookupController, generation = 0, editVersion = 0;
  function cancelLookups() {
    clearTimeout(lookupTimer); clearTimeout(geocodeTimer);
    lookupController?.abort(); geocodeController?.abort();
    generation++;
  }
  async function requestLookup(url, body, controller) {
    for (let attempt = 0; attempt < 3; attempt++) {
      controller.signal.throwIfAborted();
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }, body,
      });
      if (response.status !== 429 || attempt === 2) return response;
      await new Promise(resolve => setTimeout(resolve, 2100));
    }
  }

  function lookupAddress() {
    cancelLookups();
    const current = generation;
    const version = editVersion;
    if (!lat.value || !lng.value) return;
    addressStatus.textContent = 'กำลังค้นหาที่อยู่จากหมุด…';
    lookupTimer = setTimeout(async () => {
      const controller = new AbortController();
      lookupController = controller;
      const timeout = setTimeout(() => controller.abort(), 16000);
      try {
        const response = await requestLookup('/accounts/shop-address/',
          new URLSearchParams({ latitude: lat.value, longitude: lng.value }), controller);
        if (current !== generation || type.value !== 'mechanic') return;
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
           throw new Error('ระบบเซิร์ฟเวอร์ขัดข้อง กรุณาลองใหม่');
        }
        const data = await response.json();
        if (current !== generation || type.value !== 'mechanic') return;
        if (!response.ok) throw new Error(data.error || 'ค้นหาที่อยู่ไม่สำเร็จ กรุณากรอกที่อยู่เอง');
        if (!data.address) { addressStatus.textContent = 'ไม่พบที่อยู่บริเวณนี้ กรุณากรอกที่อยู่ร้านเอง'; return; }

        // Auto-fill always on pin update, unless user typed something DURING the fetch
        if (version === editVersion) {
          address.value = data.address;
          addressStatus.textContent = 'เติมที่อยู่จากหมุดแล้ว กรุณาตรวจสอบและแก้ไขรายละเอียดได้';
        }
      } catch (error) {
        if (current === generation && type.value === 'mechanic') {
          addressStatus.textContent = error.name === 'AbortError' ? 'ค้นหาที่อยู่นานเกินไป กรอกเองหรือลองใหม่ได้' : error.message;
        }
      } finally { clearTimeout(timeout); }
    }, 700);
  }

  let geocodeTimer, geocodeController;
  address.addEventListener('input', () => {
    editVersion++;
    cancelLookups();
    const current = generation;
    const val = address.value.trim();
    if (val.length < 3 || type.value !== 'mechanic') {
      addressStatus.textContent = '';
      return;
    }
    addressStatus.textContent = 'กำลังค้นหาหมุดจากที่อยู่…';
    geocodeTimer = setTimeout(async () => {
      const controller = new AbortController();
      geocodeController = controller;
      const timeout = setTimeout(() => controller.abort(), 16000);
      try {
        const response = await requestLookup('/accounts/shop-geocode/',
          new URLSearchParams({ address: val }), controller);
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
           throw new Error('ระบบเซิร์ฟเวอร์ขัดข้อง กรุณาลองใหม่');
        }
        const data = await response.json();
        if (current !== generation || type.value !== 'mechanic') return;
        if (!response.ok) throw new Error(data.error || 'ค้นหาพิกัดไม่สำเร็จ');
        if (data.latitude == null || data.longitude == null || !Number.isFinite(Number(data.latitude)) ||
            !Number.isFinite(Number(data.longitude)) || Math.abs(Number(data.latitude)) > 90 ||
            Math.abs(Number(data.longitude)) > 180) throw new Error('ไม่พบตำแหน่งที่ถูกต้อง กรุณาปักหมุดเอง');

        // Update pin without triggering a reverse lookup
        updatePin(Number(data.latitude), Number(data.longitude), false);
        if (marker) map.setView(marker.getLatLng(), 16);
        addressStatus.textContent = 'ปักหมุดจากที่อยู่แล้ว กรุณาตรวจสอบความถูกต้อง';
      } catch (error) {
        if (current === generation && type.value === 'mechanic') {
          addressStatus.textContent = error.name === 'AbortError' ? 'ค้นหานานเกินไป กรุณาปักหมุดเองหรือลองใหม่' : error.message;
        }
      } finally { clearTimeout(timeout); }
    }, 1500); // 1.5 second debounce for typing
  });

  refill.addEventListener('click', lookupAddress);
  let map, marker, previewUrl;
  function updatePin(latitude, longitude, lookup = true) {
    if (!map || !Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude)>90 || Math.abs(longitude)>180) return;
    lat.value = latitude.toFixed(6); lng.value = longitude.toFixed(6);
    if (!marker) {
      marker = L.marker([latitude, longitude], { draggable: true,
        icon: L.divIcon({ className: 'shop-pin', iconSize: [24,24], iconAnchor: [12,12] }) }).addTo(map);
      marker.on('dragend', () => { const p = marker.getLatLng(); updatePin(p.lat, p.lng); });
    } else marker.setLatLng([latitude, longitude]);
    status.textContent = 'ปักหมุดร้านแล้ว ลากหมุดเพื่อปรับตำแหน่งได้';
    refill.disabled = false;
    if (lookup) lookupAddress();
  }
  function restorePin() {
    if (lat.value.trim() && lng.value.trim()) {
      updatePin(Number(lat.value), Number(lng.value), false);
      if (marker) map.panTo(marker.getLatLng());
    }
  }
  function showFields() {
    const provider = type.value === 'mechanic';
    fields.hidden = !provider;
    fields.disabled = !provider;
    fields.querySelectorAll('input:not([type=hidden]),textarea').forEach(input => { input.required = provider; });
    document.getElementById('signup-submit').textContent = provider ? 'สร้างบัญชีผู้ให้บริการ' : 'สร้างบัญชีสมาชิกทั่วไป';
    if (!provider) {
      cancelLookups();
      return;
    }
    if (!window.L) { status.textContent = 'โหลดแผนที่ไม่ได้ กรุณาโหลดหน้านี้ใหม่เพื่อปักหมุด'; return; }
    if (!map) {
      map = L.map('shop-map').setView([13.7563,100.5018], 12);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map).on('tileerror', () => { status.textContent = 'โหลดภาพแผนที่ไม่สำเร็จ กรุณาลองใหม่'; });
      map.on('click', e => updatePin(e.latlng.lat, e.latlng.lng));
    }
    map.invalidateSize(); restorePin();
  }
  type.addEventListener('change', showFields);
  fields.closest('form').addEventListener('submit', event => {
    if (type.value === 'mechanic' && (!lat.value || !lng.value)) {
      event.preventDefault();
      status.textContent = 'กรุณาปักหมุดตำแหน่งร้านก่อนสร้างบัญชี';
      document.getElementById('shop-map').scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  });
  showFields();
  document.getElementById('id_shop_photo').addEventListener('change', event => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const file = event.target.files[0];
    const preview = document.getElementById('shop-photo-preview');
    preview.hidden = !file;
    if (file) { previewUrl = URL.createObjectURL(file); preview.src = previewUrl; }
  });
})();
