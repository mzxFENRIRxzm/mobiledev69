const bookingStatuses = {
  'pending': 'รอรับงาน',
  'accepted': 'รับงานแล้ว',
  'in_progress': 'กำลังซ่อม',
  'completed': 'เสร็จแล้ว',
  'cancelled': 'ยกเลิกแล้ว',
};

class Booking {
  final String shopName, cancellationReason;
  final int id;
  final String motorcycle, customer, status, problem, notes;
  final String? mechanic;
  final DateTime appointment;
  final List<BookingEvent> events;
  Booking.fromJson(Map<String, dynamic> json)
    : shopName = (json['shop_name'] as String?)?.isNotEmpty == true
          ? json['shop_name']
          : 'รายการเดิม — ยังไม่ได้เลือกร้าน',
      cancellationReason = json['cancellation_reason'] ?? '',
      id = json['id'],
      motorcycle = json['motorcycle_label'],
      customer = json['customer_name'],
      mechanic = json['mechanic_name'],
      status = json['status'],
      problem = json['problem'],
      notes = json['repair_notes'],
      appointment = DateTime.parse(json['appointment_at']).toLocal(),
      events = (json['events'] as List)
          .map((e) => BookingEvent.fromJson(e))
          .toList();
  bool get canCancel => status == 'pending' || status == 'accepted';
}

class BookingEvent {
  final String status, actor;
  final DateTime time;
  BookingEvent.fromJson(Map<String, dynamic> json)
    : status = json['status'],
      actor = json['actor'],
      time = DateTime.parse(json['created_at']).toLocal();
}

String bookingTime(DateTime value) =>
    '${value.day}/${value.month}/${value.year} '
    '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
