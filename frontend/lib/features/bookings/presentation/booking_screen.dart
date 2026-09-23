import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../../auth/auth_view_model.dart';
import '../../garage/data/garage_repository.dart';
import '../../garage/domain/motorcycle.dart';
import '../domain/booking.dart';
import 'booking_view_model.dart';
import '../../shops/data/shop_repository.dart';
import '../../shops/domain/shop.dart';

class BookingScreen extends StatelessWidget {
  final int? initialShop;
  const BookingScreen({super.key, this.initialShop});
  @override
  Widget build(BuildContext context) {
    final vm = context.watch<BookingViewModel>();
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: Text(auth.isMechanic ? 'งานซ่อมของช่าง' : 'การจองซ่อม'),
        actions: [
          IconButton(
            onPressed: () => context.go('/profile'),
            tooltip: 'โปรไฟล์ของฉัน',
            icon: const Icon(Icons.person_outline),
          ),
          TextButton(
            onPressed: () => context.go('/shops'),
            child: const Text('ร้านบริการ'),
          ),
          if (!auth.isMechanic)
            TextButton(
              onPressed: () => context.go('/garage'),
              child: const Text('โรงรถ'),
            ),
          IconButton(
            onPressed: auth.logout,
            tooltip: 'ออกจากระบบทุกอุปกรณ์',
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'THE_X · ${auth.username}',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              Text(
                auth.isMechanic
                    ? 'งานของร้านคุณ · เริ่มและปิดงานได้โดยช่างผู้รับงาน'
                    : 'เลือกนัดหมายและติดตามการดูแลรถของคุณ',
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                children: [
                  if (!auth.isMechanic)
                    FilledButton.icon(
                      onPressed: vm.busy || vm.loading
                          ? null
                          : () => showDialog<void>(
                              context: context,
                              builder: (_) => BookingForm(
                                vm: vm,
                                shops: ShopRepository(
                                  context.read<ApiService>(),
                                ),
                                initialShop: initialShop,
                                garage: GarageRepository(
                                  context.read<ApiService>(),
                                ),
                              ),
                            ),
                      icon: const Icon(Icons.add),
                      label: const Text('จองซ่อม'),
                    ),
                  OutlinedButton.icon(
                    onPressed: vm.loading || vm.busy ? null : vm.load,
                    icon: const Icon(Icons.refresh),
                    label: const Text('โหลดใหม่'),
                  ),
                ],
              ),
              if (vm.loading || vm.busy) const LinearProgressIndicator(),
              if (vm.error != null || auth.error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    vm.error ?? auth.error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (!vm.loading && vm.bookings.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(32),
                  child: Text('ยังไม่มีรายการจองซ่อม'),
                ),
              for (final booking in vm.bookings)
                Card(
                  key: ValueKey('booking-${booking.id}'),
                  child: ExpansionTile(
                    key: ValueKey(booking.id),
                    title: Text('#${booking.id} · ${booking.motorcycle}'),
                    subtitle: Text(
                      '${bookingStatuses[booking.status]} · ${bookingTime(booking.appointment)}',
                    ),
                    childrenPadding: const EdgeInsets.all(16),
                    expandedCrossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('ร้าน: ${booking.shopName}'),
                      if (booking.cancellationReason.isNotEmpty)
                        Text('เหตุผลที่ยกเลิก: ${booking.cancellationReason}'),
                      Text(
                        'ลูกค้า: ${booking.customer} · ช่าง: ${booking.mechanic ?? 'ยังไม่มีผู้รับงาน'}',
                      ),
                      const SizedBox(height: 12),
                      Text('อาการ / สิ่งที่ต้องการให้ตรวจ\n${booking.problem}'),
                      if (booking.notes.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: Text('ผลการซ่อม\n${booking.notes}'),
                        ),
                      const Divider(),
                      for (final event in booking.events)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text(
                            '${bookingStatuses[event.status]} · ${event.actor} · ${bookingTime(event.time)}',
                          ),
                        ),
                      const SizedBox(height: 12),
                      if (booking.canCancel)
                        OutlinedButton(
                          onPressed: vm.busy
                              ? null
                              : () => _transition(
                                  context,
                                  vm,
                                  booking,
                                  'cancel',
                                  'ยกเลิกการจอง',
                                ),
                          child: const Text('ยกเลิกการจอง'),
                        ),
                      if (auth.isMechanic && booking.status == 'pending')
                        FilledButton(
                          onPressed: vm.busy
                              ? null
                              : () => _transition(
                                  context,
                                  vm,
                                  booking,
                                  'accept',
                                  'รับงาน',
                                ),
                          child: const Text('รับงาน'),
                        ),
                      if (auth.isMechanic &&
                          booking.mechanic == auth.username &&
                          booking.status == 'accepted')
                        FilledButton(
                          onPressed: vm.busy
                              ? null
                              : () => _transition(
                                  context,
                                  vm,
                                  booking,
                                  'start',
                                  'เริ่มซ่อม',
                                ),
                          child: const Text('เริ่มซ่อม'),
                        ),
                      if (auth.isMechanic &&
                          booking.mechanic == auth.username &&
                          booking.status == 'in_progress')
                        FilledButton(
                          onPressed: vm.busy
                              ? null
                              : () => _transition(
                                  context,
                                  vm,
                                  booking,
                                  'complete',
                                  'ปิดงานซ่อม',
                                ),
                          child: const Text('ปิดงานซ่อม'),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _transition(
    BuildContext context,
    BookingViewModel vm,
    Booking booking,
    String action,
    String label,
  ) async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => TransitionDialog(
        vm: vm,
        booking: booking,
        action: action,
        label: label,
      ),
    );
  }
}

class TransitionDialog extends StatefulWidget {
  final BookingViewModel vm;
  final Booking booking;
  final String action, label;
  const TransitionDialog({
    super.key,
    required this.vm,
    required this.booking,
    required this.action,
    required this.label,
  });
  @override
  State<TransitionDialog> createState() => _TransitionDialogState();
}

class _TransitionDialogState extends State<TransitionDialog> {
  final notes = TextEditingController();
  bool saving = false;
  String? error;
  @override
  void dispose() {
    notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !saving,
    child: AlertDialog(
      title: Text('${widget.label} #${widget.booking.id}'),
      content: SizedBox(
        width: 480,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.booking.motorcycle),
            if (widget.action == 'complete' || widget.action == 'cancel')
              TextField(
                controller: notes,
                enabled: !saving,
                maxLength: widget.action == 'cancel' ? 1000 : 2000,
                minLines: 3,
                maxLines: 5,
                decoration: InputDecoration(
                  labelText: widget.action == 'cancel'
                      ? 'เหตุผลที่ยกเลิก (ร้านต้องระบุ)'
                      : 'รายละเอียดงานซ่อม',
                ),
              ),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: saving ? null : () => Navigator.pop(context),
          child: const Text('กลับ'),
        ),
        FilledButton(
          onPressed: saving
              ? null
              : () async {
                  if (widget.action == 'complete' &&
                      notes.text.trim().isEmpty) {
                    setState(() => error = 'กรุณาระบุรายละเอียดงานซ่อม');
                    return;
                  }
                  setState(() {
                    saving = true;
                    error = null;
                  });
                  final message = await widget.vm.transition(
                    widget.booking.id,
                    widget.action,
                    notes.text,
                  );
                  if (!context.mounted) return;
                  if (message == null) {
                    Navigator.pop(context);
                  } else {
                    setState(() {
                      error = message;
                      saving = false;
                    });
                  }
                },
          child: Text(saving ? 'กำลังบันทึก…' : 'ยืนยัน'),
        ),
      ],
    ),
  );
}

class BookingForm extends StatefulWidget {
  final BookingViewModel vm;
  final GarageRepository garage;
  final ShopRepository shops;
  final int? initialShop;
  const BookingForm({
    super.key,
    required this.vm,
    required this.garage,
    required this.shops,
    this.initialShop,
  });
  @override
  State<BookingForm> createState() => _BookingFormState();
}

class _BookingFormState extends State<BookingForm> {
  final form = GlobalKey<FormState>();
  final problem = TextEditingController();
  List<Motorcycle> bikes = [];
  List<Shop> shops = [];
  int? shop;
  int? bike;
  DateTime? appointment;
  bool loading = true, saving = false;
  String? error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    final result = await widget.garage.list();
    final shopResult = await widget.shops.list();
    if (!mounted) return;
    setState(() {
      loading = false;
      if (result is Success<List<Motorcycle>>) bikes = result.value;
      if (result is Failure<List<Motorcycle>>) error = result.message;
      if (shopResult is Success<List<Shop>>) {
        shops = shopResult.value.where((s) => s.acceptingBookings).toList();
        final preferred = shop ?? widget.initialShop;
        shop = shops.any((s) => s.id == preferred) ? preferred : null;
      }
      if (shopResult is Failure<List<Shop>>) error = shopResult.message;
    });
  }

  @override
  void dispose() {
    problem.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !saving,
    child: AlertDialog(
      title: const Text('จองซ่อม'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('วันเวลาเป็นคำขอนัดหมาย กรุณารอช่างรับงาน'),
                const SizedBox(height: 16),
                if (loading) const LinearProgressIndicator(),
                if (!loading && shops.isEmpty)
                  const Text('ยังไม่มีร้านเปิดรับการจอง'),
                DropdownButtonFormField<int>(
                  key: ValueKey('shop-$loading'),
                  initialValue: shop,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'ร้านที่ต้องการรับบริการ',
                  ),
                  items: [
                    for (final s in shops)
                      DropdownMenuItem(
                        value: s.id,
                        child: Text(s.name, overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: saving || loading
                      ? null
                      : (value) => setState(() => shop = value),
                  validator: (value) => value == null ? 'กรุณาเลือกร้าน' : null,
                ),
                for (final s in shops.where((s) => s.id == shop))
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text('${s.address}\nโทร: ${s.phone}'),
                  ),
                const SizedBox(height: 16),
                if (!loading && bikes.isEmpty)
                  const Text('ยังไม่มีรถ กรุณาเพิ่มรถในโรงรถก่อนจอง'),
                DropdownButtonFormField<int>(
                  initialValue: bike,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'รถที่ต้องการซ่อม',
                  ),
                  items: [
                    for (final item in bikes)
                      DropdownMenuItem(
                        value: item.id,
                        child: Text(
                          '${item.brand} ${item.model} · ${item.plate}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: saving
                      ? null
                      : (value) => setState(() => bike = value),
                  validator: (value) => value == null ? 'กรุณาเลือกรถ' : null,
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: saving
                      ? null
                      : () async {
                          final now = DateTime.now();
                          final date = await showDatePicker(
                            context: context,
                            initialDate: now.add(const Duration(days: 1)),
                            firstDate: now,
                            lastDate: now.add(const Duration(days: 365)),
                          );
                          if (date == null || !context.mounted) return;
                          final time = await showTimePicker(
                            context: context,
                            initialTime: const TimeOfDay(hour: 9, minute: 0),
                          );
                          if (time != null && mounted) {
                            setState(
                              () => appointment = DateTime(
                                date.year,
                                date.month,
                                date.day,
                                time.hour,
                                time.minute,
                              ),
                            );
                          }
                        },
                  icon: const Icon(Icons.calendar_month),
                  label: Text(
                    appointment == null
                        ? 'เลือกวันและเวลานัดหมาย'
                        : bookingTime(appointment!),
                  ),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: problem,
                  enabled: !saving,
                  minLines: 3,
                  maxLines: 5,
                  maxLength: 2000,
                  decoration: const InputDecoration(
                    labelText: 'อาการ / สิ่งที่ต้องการให้ตรวจ',
                  ),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'กรุณาระบุอาการ'
                      : null,
                ),
                if (error != null)
                  Text(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                if (!loading &&
                    (bikes.isEmpty || shops.isEmpty || error != null))
                  TextButton(
                    onPressed: saving ? null : _load,
                    child: const Text('โหลดข้อมูลใหม่'),
                  ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: saving ? null : () => Navigator.pop(context),
          child: const Text('ยกเลิก'),
        ),
        FilledButton(
          onPressed: loading || saving || bikes.isEmpty || shops.isEmpty
              ? null
              : () async {
                  if (!form.currentState!.validate()) return;
                  if (appointment == null ||
                      !appointment!.isAfter(DateTime.now())) {
                    setState(() => error = 'กรุณาเลือกวันเวลาในอนาคต');
                    return;
                  }
                  setState(() {
                    saving = true;
                    error = null;
                  });
                  final message = await widget.vm.create(
                    bike!,
                    appointment!,
                    problem.text,
                    shop!,
                  );
                  if (!context.mounted) return;
                  if (message == null) {
                    Navigator.pop(context);
                  } else {
                    setState(() {
                      saving = false;
                      error = message;
                    });
                  }
                },
          child: Text(saving ? 'กำลังบันทึก…' : 'บันทึกการจอง'),
        ),
      ],
    ),
  );
}
