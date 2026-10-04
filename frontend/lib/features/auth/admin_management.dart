import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../core/api/api_service.dart';

String adminError(Object error) =>
    error is StateError ? error.message.toString() : describeError(error);

Future<bool> editAdminUser(BuildContext context, ApiService api,
    Map<String, dynamic> user) async {
  final fields = <String, TextEditingController>{
    for (final name in ['username', 'first_name', 'last_name', 'email', 'phone'])
      name: TextEditingController(text: '${user[name] ?? ''}'),
  };
  var role = user['role'] as String;
  var active = user['is_active'] == true;
  final form = GlobalKey<FormState>();
  final saved = await showDialog<bool>(context: context, builder: (dialog) =>
    StatefulBuilder(builder: (context, update) => AlertDialog(
      title: Text('แก้ไขผู้ใช้ ${user['username']}'),
      content: SizedBox(width: 480, child: SingleChildScrollView(child: Form(
        key: form, child: Column(mainAxisSize: MainAxisSize.min, children: [
          for (final entry in <String, String>{
            'username': 'ชื่อผู้ใช้', 'first_name': 'ชื่อ', 'last_name': 'นามสกุล',
            'email': 'อีเมล', 'phone': 'เบอร์โทรศัพท์',
          }.entries)
            TextFormField(controller: fields[entry.key],
              decoration: InputDecoration(labelText: entry.value),
              validator: (value) => entry.key == 'username' &&
                  (value == null || value.trim().isEmpty)
                  ? 'กรุณากรอกชื่อผู้ใช้' : null),
          DropdownButtonFormField<String>(initialValue: role,
            decoration: const InputDecoration(labelText: 'บทบาท'),
            items: const [
              DropdownMenuItem(value: 'customer', child: Text('สมาชิกทั่วไป')),
              DropdownMenuItem(value: 'mechanic', child: Text('ผู้ให้บริการ')),
              DropdownMenuItem(value: 'admin', child: Text('Admin')),
            ], onChanged: (value) { if (value != null) update(() => role = value); }),
          SwitchListTile(title: const Text('บัญชีใช้งานได้'), value: active,
            onChanged: (value) => update(() => active = value)),
        ])),)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
        FilledButton(onPressed: () {
          if (form.currentState!.validate()) Navigator.pop(dialog, true);
        }, child: const Text('บันทึก')),
      ],
    )));
  try {
    if (saved != true) return false;
    await api.request('admin/users/${user['id']}/', method: 'PATCH', data: {
      for (final entry in fields.entries) entry.key: entry.value.text.trim(),
      'role': role, 'is_active': active,
    });
    return true;
  } finally {
    for (final controller in fields.values) { controller.dispose(); }
  }
}

Future<bool> editAdminMotorcycles(BuildContext context, ApiService api,
    Map<String, dynamic> user) async {
  final rows = (await api.request('admin/users/${user['id']}/motorcycles/') as List)
      .map((item) => Map<String, dynamic>.from(item as Map)).toList();
  if (!context.mounted) return false;
  if (rows.isEmpty) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('ผู้ใช้นี้ยังไม่มีรถในโรงรถ')));
    return false;
  }
  final selected = await showDialog<Map<String, dynamic>>(context: context,
    builder: (dialog) => AlertDialog(title: Text('รถของ ${user['username']}'),
      content: SizedBox(width: 420, height: 300, child: ListView(children: [
        for (final row in rows) ListTile(
          title: Text('${row['brand']} ${row['model']}'),
          subtitle: Text('${row['license_plate']}${row['archived_at'] == null ? '' : ' · ซ่อนอยู่'}'),
          trailing: IconButton(
            tooltip: row['archived_at'] == null ? 'ซ่อนรถ' : 'คืนรถ',
            icon: Icon(row['archived_at'] == null ? Icons.archive_outlined : Icons.unarchive_outlined),
            onPressed: () => Navigator.pop(dialog, {...row, '_archive': true})),
          onTap: () => Navigator.pop(dialog, row)),
      ])),
      actions: [TextButton(onPressed: () => Navigator.pop(dialog),
        child: const Text('ปิด'))]));
  if (selected == null || !context.mounted) return false;
  if (selected['_archive'] == true) {
    final archiving = selected['archived_at'] == null;
    final reason = TextEditingController();
    final confirmed = await showDialog<bool>(context: context,
      builder: (dialog) => AlertDialog(
        title: Text(archiving ? 'ซ่อนรถ ${selected['license_plate']}' :
          'คืนรถ ${selected['license_plate']}'),
        content: archiving ? TextField(controller: reason,
          decoration: const InputDecoration(labelText: 'เหตุผล (จำเป็น)')) :
          const Text('รถจะกลับมาแสดงในโรงรถของผู้ใช้'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('ยืนยัน')),
        ]));
    try {
      if (confirmed != true) return false;
      if (archiving && reason.text.trim().isEmpty) throw StateError('กรุณาระบุเหตุผล');
      await api.request('admin/users/${user['id']}/motorcycles/${selected['id']}/archive/',
        method: 'POST', data: {
          'action': archiving ? 'archive' : 'restore', 'reason': reason.text.trim(),
        });
      return true;
    } finally {
      reason.dispose();
    }
  }
  if (selected['archived_at'] != null) return false;
  final fields = <String, TextEditingController>{
    for (final name in ['brand', 'model', 'license_plate', 'year', 'mileage', 'notes'])
      name: TextEditingController(text: '${selected[name] ?? ''}'),
  };
  final form = GlobalKey<FormState>();
  final saved = await showDialog<bool>(context: context, builder: (dialog) =>
    AlertDialog(title: Text('แก้ไขรถ ${selected['license_plate']}'),
      content: SizedBox(width: 440, child: SingleChildScrollView(child: Form(
        key: form, child: Column(mainAxisSize: MainAxisSize.min, children: [
          for (final entry in <String, String>{
            'brand': 'ยี่ห้อ', 'model': 'รุ่น', 'license_plate': 'ทะเบียน',
            'year': 'ปี', 'mileage': 'เลขไมล์', 'notes': 'หมายเหตุ',
          }.entries)
            TextFormField(controller: fields[entry.key],
              keyboardType: ['year', 'mileage'].contains(entry.key)
                  ? TextInputType.number : TextInputType.text,
              decoration: InputDecoration(labelText: entry.value),
              validator: (value) {
                if (['brand', 'model', 'license_plate', 'year'].contains(entry.key) &&
                    (value == null || value.trim().isEmpty)) {
                  return 'กรุณากรอก ${entry.value}';
                }
                if (entry.key == 'year' && int.tryParse(value ?? '') == null) {
                  return 'ปีไม่ถูกต้อง';
                }
                if (entry.key == 'mileage' && (value ?? '').isNotEmpty &&
                    int.tryParse(value!) == null) {
                  return 'เลขไมล์ไม่ถูกต้อง';
                }
                return null;
              }),
        ])),)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
        FilledButton(onPressed: () {
          if (form.currentState!.validate()) Navigator.pop(dialog, true);
        }, child: const Text('บันทึก')),
      ]));
  try {
    if (saved != true) return false;
    await api.request('admin/users/${user['id']}/motorcycles/${selected['id']}/',
      method: 'PATCH', data: {
        for (final name in ['brand', 'model', 'license_plate', 'notes'])
          name: fields[name]!.text.trim(),
        'year': int.parse(fields['year']!.text.trim()),
        'mileage': fields['mileage']!.text.trim().isEmpty
            ? 0 : int.parse(fields['mileage']!.text.trim()),
      });
    return true;
  } finally {
    for (final controller in fields.values) { controller.dispose(); }
  }
}

Future<bool> editAdminShop(BuildContext context, ApiService api,
    Map<String, dynamic> shop) async {
  final fields = <String, TextEditingController>{
    for (final name in ['name', 'address', 'phone', 'description'])
      name: TextEditingController(text: '${shop[name] ?? ''}'),
  };
  var accepting = shop['accepting_bookings'] == true;
  var lat = double.tryParse('${shop['latitude'] ?? ''}');
  var lon = double.tryParse('${shop['longitude'] ?? ''}');
  XFile? photo;
  final form = GlobalKey<FormState>();
  final saved = await showDialog<bool>(context: context, builder: (dialog) =>
    StatefulBuilder(builder: (context, update) => AlertDialog(
      title: Text('แก้ไขร้าน ${shop['name']}'),
      content: SizedBox(width: 600, height: 570,
        child: SingleChildScrollView(child: Form(key: form,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            for (final entry in <String, String>{
              'name': 'ชื่อร้าน', 'address': 'ที่อยู่', 'phone': 'โทรศัพท์',
              'description': 'รายละเอียด',
            }.entries)
              TextFormField(controller: fields[entry.key],
                maxLines: entry.key == 'description' ? 3 : 1,
                decoration: InputDecoration(labelText: entry.value),
                validator: (value) => ['name', 'address', 'phone'].contains(entry.key) &&
                    (value == null || value.trim().isEmpty)
                    ? 'กรุณากรอก ${entry.value}' : null),
            SwitchListTile(title: const Text('ร้านเปิดรับจอง'), value: accepting,
              onChanged: (value) => update(() => accepting = value)),
            Row(children: [
              OutlinedButton.icon(icon: const Icon(Icons.image_outlined),
                label: const Text('เปลี่ยนรูปร้าน'), onPressed: () async {
                  final picked = await openFile(acceptedTypeGroups: [
                    const XTypeGroup(label: 'รูปภาพ',
                      extensions: ['jpg', 'jpeg', 'png', 'webp'],
                      mimeTypes: ['image/jpeg', 'image/png', 'image/webp']),
                  ]);
                  if (picked != null) update(() => photo = picked);
                }),
              const SizedBox(width: 10),
              Expanded(child: Text(photo?.name ??
                (shop['photo'] == null ? 'ยังไม่มีรูป' : 'ใช้รูปเดิม'),
                overflow: TextOverflow.ellipsis)),
            ]),
            const SizedBox(height: 10),
            const Text('แตะแผนที่เพื่อย้ายหมุดร้าน'),
            SizedBox(height: 220, child: FlutterMap(
              options: MapOptions(initialCenter: LatLng(lat ?? 13.7563, lon ?? 100.5018),
                initialZoom: lat == null ? 5 : 14,
                onTap: (_, point) => update(() { lat = point.latitude; lon = point.longitude; })),
              children: [
                TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.the_x.mobiledev69'),
                if (lat != null && lon != null) MarkerLayer(markers: [
                  Marker(point: LatLng(lat!, lon!), width: 42, height: 42,
                    child: const Icon(Icons.location_pin, color: Colors.red, size: 42)),
                ]),
              ])),
            if (lat != null) Text('หมุด: ${lat!.toStringAsFixed(5)}, ${lon!.toStringAsFixed(5)}'),
          ])))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
        FilledButton(onPressed: () {
          if (form.currentState!.validate()) Navigator.pop(dialog, true);
        }, child: const Text('บันทึก')),
      ],
    )));
  try {
    if (saved != true) return false;
    final payload = <String, dynamic>{
      for (final entry in fields.entries) entry.key: entry.value.text.trim(),
      'accepting_bookings': accepting,
      'latitude': ?lat,
      'longitude': ?lon,
    };
    if (photo != null) {
      final bytes = await photo!.readAsBytes();
      if (bytes.length > 5 * 1024 * 1024) {
        throw StateError('รูปร้านต้องไม่เกิน 5 MB');
      }
      payload['photo'] = MultipartFile.fromBytes(bytes, filename: photo!.name);
    }
    await api.request('admin/shops/${shop['id']}/details/', method: 'PATCH',
      data: photo == null ? payload : FormData.fromMap(payload));
    return true;
  } finally {
    for (final controller in fields.values) { controller.dispose(); }
  }
}

Future<bool> moderateAdminShop(BuildContext context, ApiService api,
    Map<String, dynamic> shop) async {
  var action = 'suspend';
  final reason = TextEditingController();
  DateTime? until;
  final saved = await showDialog<bool>(context: context, builder: (dialog) =>
    StatefulBuilder(builder: (context, update) => AlertDialog(
      title: Text('จัดการสถานะ ${shop['name']}'),
      content: SizedBox(width: 460, child: Column(mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(initialValue: action,
            decoration: const InputDecoration(labelText: 'การดำเนินการ'),
            items: const [
              DropdownMenuItem(value: 'suspend', child: Text('ระงับชั่วคราว')),
              DropdownMenuItem(value: 'ban', child: Text('แบนจนกว่า Admin จะคืนสถานะ')),
              DropdownMenuItem(value: 'restore', child: Text('คืนสถานะ')),
              DropdownMenuItem(value: 'delete', child: Text('ซ่อนถาวร เก็บประวัติ')),
            ], onChanged: (value) { if (value != null) update(() => action = value); }),
          if (action == 'suspend') OutlinedButton.icon(
            icon: const Icon(Icons.calendar_month),
            label: Text(until == null ? 'เลือกวันและเวลาสิ้นสุด' : '$until'),
            onPressed: () async {
              final day = await showDatePicker(context: dialog,
                firstDate: DateTime.now(), lastDate: DateTime.now().add(const Duration(days: 365)),
                initialDate: until ?? DateTime.now().add(const Duration(days: 1)));
              if (day == null || !dialog.mounted) return;
              final time = await showTimePicker(context: dialog,
                initialTime: TimeOfDay.fromDateTime(until ?? DateTime.now().add(const Duration(days: 1))));
              if (time != null) {
                update(() => until = DateTime(day.year, day.month, day.day,
                  time.hour, time.minute));
              }
            }),
          if (action != 'restore') TextField(controller: reason, maxLines: 2,
            decoration: const InputDecoration(labelText: 'เหตุผล (จำเป็น)')),
          if (action == 'delete') const Padding(padding: EdgeInsets.only(top: 12),
            child: Text('ร้านจะไม่ปรากฏในแอปอีก การจองและแชตเก่ายังอยู่ การกระทำนี้ย้อนกลับไม่ได้')),
        ])),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
        FilledButton(onPressed: () {
          if ((action != 'restore' && reason.text.trim().isEmpty) ||
              (action == 'suspend' && (until == null || !until!.isAfter(DateTime.now())))) {
            ScaffoldMessenger.of(dialog).showSnackBar(const SnackBar(
              content: Text('กรุณากรอกเหตุผลและเวลาสิ้นสุดที่ถูกต้อง')));
            return;
          }
          Navigator.pop(dialog, true);
        }, child: const Text('ยืนยัน')),
      ],
    )));
  try {
    if (saved != true) return false;
    await api.request('admin/shops/${shop['id']}/moderate/', method: 'POST', data: {
      'action': action, 'reason': reason.text.trim(),
      if (action == 'suspend') 'suspended_until': until!.toUtc().toIso8601String(),
    });
    return true;
  } finally {
    reason.dispose();
  }
}
