import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';
import 'admin_management.dart';

String bookingStatusLabel(Object? value) => switch (value) {
  'pending' => 'รอร้านรับงาน',
  'accepted' => 'รับงานแล้ว',
  'in_progress' => 'กำลังซ่อม',
  'completed' => 'ซ่อมเสร็จ',
  'cancelled' => 'ยกเลิก',
  _ => '$value',
};

Future<void> showAdminBooking(BuildContext context, ApiService api, int id,
    {VoidCallback? onChanged}) async {
  final data = Map<String, dynamic>.from(
    await api.request('admin/bookings/$id/') as Map);
  if (!context.mounted) return;
  Widget line(String label, Object? value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: SelectableText('$label: ${value == null || value == '' ? '—' : value}'));
  final customer = Map<String, dynamic>.from(data['customer'] as Map);
  final shop = Map<String, dynamic>.from(data['shop'] as Map);
  final bike = Map<String, dynamic>.from(data['motorcycle'] as Map);
  final mechanic = data['mechanic'] as Map?;
  await showDialog<void>(context: context, builder: (dialog) => AlertDialog(
    title: Text('รายละเอียดการจอง #$id'),
    content: SizedBox(width: math.min(650, MediaQuery.sizeOf(dialog).width - 64),
      height: math.min(620, MediaQuery.sizeOf(dialog).height * 0.65),
      child: ListView(children: [
        line('สถานะ', bookingStatusLabel(data['status'])),
        line('เวลานัด', data['appointment_at']),
        line('เวลาสร้าง', data['created_at']),
        line('แก้ไขล่าสุด', data['updated_at']),
        const Divider(),
        Text('ลูกค้า', style: Theme.of(dialog).textTheme.titleMedium),
        line('ชื่อผู้ใช้', customer['username']),
        line('ชื่อจริง', customer['name']),
        line('อีเมล', customer['email']),
        line('โทรศัพท์', customer['phone']),
        const Divider(),
        Text('รถและร้าน', style: Theme.of(dialog).textTheme.titleMedium),
        line('รถ ณ วันจอง', data['motorcycle_label']),
        line('ข้อมูลรถปัจจุบัน',
          '${bike['brand']} ${bike['model']} · ${bike['license_plate']} · ${bike['year']}'),
        line('เลขไมล์ปัจจุบัน', bike['mileage']),
        line('ร้าน', shop['name']),
        line('ที่อยู่ร้าน', shop['address']),
        line('โทรศัพท์ร้าน', shop['phone']),
        line('ช่างที่รับงาน', mechanic?['username']),
        const Divider(),
        Text('งานซ่อม', style: Theme.of(dialog).textTheme.titleMedium),
        line('อาการที่แจ้ง', data['problem']),
        line('รายละเอียดการซ่อม', data['repair_notes']),
        line('เหตุผลที่ยกเลิก', data['cancellation_reason']),
        if (data['archived_at'] != null) line('ซ่อนเมื่อ', data['archived_at']),
        if (data['archive_reason'] != null) line('เหตุผลที่ซ่อน', data['archive_reason']),
        const Divider(),
        Text('ประวัติสถานะ', style: Theme.of(dialog).textTheme.titleMedium),
        for (final event in data['events'] as List)
          line('${event['created_at']}',
            '${bookingStatusLabel(event['status'])} · ${event['actor']}'),
      ])),
    actions: [
      if (data['archived_at'] == null) TextButton(
        onPressed: () async {
          try {
            final changed = await _correctBooking(dialog, api, id, data);
            if (changed && dialog.mounted) {
              Navigator.pop(dialog);
              onChanged?.call();
            }
          } catch (error) {
            if (dialog.mounted) {
              ScaffoldMessenger.of(dialog).showSnackBar(
                SnackBar(content: Text(adminError(error))));
            }
          }
        }, child: const Text('แก้ไขข้อมูล')),
      if (data['archived_at'] == null &&
          ['pending', 'accepted', 'cancelled', 'completed'].contains(data['status']))
        TextButton(onPressed: () async {
          try {
            final action = ['pending', 'accepted'].contains(data['status'])
                ? 'cancel' : 'archive';
            final changed = await _bookingAction(dialog, api, id, action);
            if (changed && dialog.mounted) {
              Navigator.pop(dialog);
              onChanged?.call();
            }
          } catch (error) {
            if (dialog.mounted) {
              ScaffoldMessenger.of(dialog).showSnackBar(
                SnackBar(content: Text(adminError(error))));
            }
          }
        }, child: Text(['pending', 'accepted'].contains(data['status'])
          ? 'ยกเลิกการจอง' : 'ซ่อนรายการ')),
      TextButton(onPressed: () => Navigator.pop(dialog), child: const Text('ปิด')),
    ],
  ));
}

Future<bool> _correctBooking(BuildContext context, ApiService api, int id,
    Map<String, dynamic> data) async {
  final appointment = TextEditingController(text: '${data['appointment_at']}');
  final problem = TextEditingController(text: '${data['problem']}');
  final notes = TextEditingController(text: '${data['repair_notes']}');
  final saved = await showDialog<bool>(context: context, builder: (dialog) => AlertDialog(
    title: Text('แก้ไขการจอง #$id'),
    content: SizedBox(width: math.min(500, MediaQuery.sizeOf(dialog).width - 64),
      child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
      TextField(controller: appointment,
        decoration: const InputDecoration(labelText: 'เวลานัด (ISO 8601)')),
      TextField(controller: problem, maxLines: 3,
        decoration: const InputDecoration(labelText: 'อาการที่แจ้ง')),
      TextField(controller: notes, maxLines: 3,
        decoration: const InputDecoration(labelText: 'รายละเอียดงานซ่อม')),
    ]))),
    actions: [
      TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
      FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('บันทึก')),
    ]));
  try {
    if (saved != true) return false;
    final date = DateTime.tryParse(appointment.text.trim());
    if (date == null || problem.text.trim().isEmpty) {
      throw StateError('กรุณากรอกเวลานัดและอาการให้ถูกต้อง');
    }
    await api.request('admin/bookings/$id/', method: 'PATCH', data: {
      'appointment_at': date.toUtc().toIso8601String(),
      'problem': problem.text.trim(), 'repair_notes': notes.text.trim(),
    });
    return true;
  } finally {
    appointment.dispose(); problem.dispose(); notes.dispose();
  }
}

Future<bool> _bookingAction(BuildContext context, ApiService api,
    int id, String action) async {
  final reason = TextEditingController();
  final saved = await showDialog<bool>(context: context, builder: (dialog) => AlertDialog(
    title: Text(action == 'cancel' ? 'ยกเลิกการจอง #$id' : 'ซ่อนการจอง #$id'),
    content: Column(mainAxisSize: MainAxisSize.min, children: [
      if (action == 'archive') const Text('รายการจะหายจากแอปของผู้ใช้ แต่เก็บประวัติไว้ใน Admin'),
      TextField(controller: reason, maxLines: 2,
        decoration: const InputDecoration(labelText: 'เหตุผล (จำเป็น)')),
    ]),
    actions: [
      TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
      FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('ยืนยัน')),
    ]));
  try {
    if (saved != true) return false;
    if (reason.text.trim().isEmpty) throw StateError('กรุณาระบุเหตุผล');
    await api.request('admin/bookings/$id/action/', method: 'POST',
      data: {'action': action, 'reason': reason.text.trim()});
    return true;
  } finally {
    reason.dispose();
  }
}
