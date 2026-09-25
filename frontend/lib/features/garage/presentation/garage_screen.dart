import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../../auth/auth_view_model.dart';
import '../../auth/app_menu.dart';
import '../domain/motorcycle.dart';
import 'garage_view_model.dart';
import 'customer_overview.dart';

class GarageScreen extends StatelessWidget {
  const GarageScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final vm = context.watch<GarageViewModel>();
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'THE_X',
          style: TextStyle(letterSpacing: 4, fontWeight: FontWeight.w900),
        ),
        actions: [
          IconButton(
            onPressed: () => context.go('/ai-chat'),
            tooltip: 'แชต AI',
            icon: const Icon(Icons.smart_toy_outlined),
          ),
          IconButton(
            onPressed: () => context.go('/messages'),
            tooltip: 'แชตข้อความ',
            icon: const Icon(Icons.chat_bubble_outline),
          ),
          const AppMenu(),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1050),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'ยินดีต้อนรับ ${auth.username}',
                style: TextStyle(color: Theme.of(context).colorScheme.primary),
              ),
              const SizedBox(height: 12),
              const Text(
                'โรงรถของฉัน',
                style: TextStyle(fontSize: 34, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                '${vm.motorcycles.length} คัน · ดูแลรถให้พร้อมสำหรับทุกเส้นทาง',
                style: const TextStyle(color: Colors.white60),
              ),
              const SizedBox(height: 28),
              const CustomerOverview(),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      onChanged: vm.search,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        hintText: 'ค้นหายี่ห้อ รุ่น หรือทะเบียน',
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    onPressed: vm.loading ? null : vm.load,
                    tooltip: 'โหลดใหม่',
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.icon(
                  onPressed: () => _edit(context, vm),
                  icon: const Icon(Icons.add),
                  label: const Text('เพิ่มรถของฉัน'),
                ),
              ),
              if (vm.loading)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: LinearProgressIndicator(),
                ),
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
              const SizedBox(height: 20),
              if (!vm.loading && vm.filtered.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    children: [
                      const Icon(
                        Icons.two_wheeler,
                        size: 64,
                        color: Colors.white38,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        vm.query.isEmpty
                            ? 'เพิ่มรถคันแรกเพื่อเริ่มต้นโรงรถของคุณ'
                            : 'ไม่พบรถที่ตรงกับคำค้น',
                      ),
                    ],
                  ),
                ),
              ...vm.filtered.map(
                (bike) => Card(
                  margin: const EdgeInsets.only(bottom: 14),
                  child: ListTile(
                    contentPadding: const EdgeInsets.all(20),
                    leading: Icon(
                      Icons.two_wheeler,
                      color: Theme.of(context).colorScheme.primary,
                      size: 36,
                    ),
                    title: Text(
                      '${bike.brand} ${bike.model}',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: Text(
                      '${bike.plate} · ปี ${bike.year}\n${bike.mileage} กม.',
                      style: const TextStyle(height: 1.7),
                    ),
                    isThreeLine: true,
                    onTap: () => _detail(context, vm, bike),
                    trailing: const Icon(Icons.chevron_right),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _detail(
    BuildContext context,
    GarageViewModel vm,
    Motorcycle bike,
  ) => showDialog<void>(
    context: context,
    builder: (dialog) => AlertDialog(
      title: Text('${bike.brand} ${bike.model}'),
      content: Text(
        'ทะเบียน ${bike.plate}\nปี ${bike.year}\nเลขไมล์ ${bike.mileage} กม.\n\n${bike.notes.isEmpty ? 'ไม่มีหมายเหตุ' : bike.notes}',
      ),
      actions: [
        TextButton(
          onPressed: () async {
            Navigator.pop(dialog);
            final confirmed = await showDialog<bool>(
              context: context,
              builder: (confirm) => AlertDialog(
                title: const Text('ลบรถคันนี้?'),
                content: Text('ข้อมูล ${bike.plate} จะถูกลบออกจากโรงรถ'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(confirm, false),
                    child: const Text('ยกเลิก'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(confirm, true),
                    child: const Text('ยืนยันลบ'),
                  ),
                ],
              ),
            );
            if (confirmed == true) await vm.delete(bike.id);
          },
          child: const Text('ลบรถ'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.pop(dialog);
            _edit(context, vm, bike);
          },
          child: const Text('แก้ไข'),
        ),
      ],
    ),
  );
  Future<void> _edit(
    BuildContext context,
    GarageViewModel vm, [
    Motorcycle? bike,
  ]) => showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => MotorcycleForm(vm: vm, bike: bike),
  );
}

class MotorcycleForm extends StatefulWidget {
  final GarageViewModel vm;
  final Motorcycle? bike;
  const MotorcycleForm({super.key, required this.vm, this.bike});
  @override
  State<MotorcycleForm> createState() => _MotorcycleFormState();
}

class _MotorcycleFormState extends State<MotorcycleForm> {
  final form = GlobalKey<FormState>();
  late final List<TextEditingController> fields;
  bool saving = false;
  String? error;
  @override
  void initState() {
    super.initState();
    final b = widget.bike;
    fields = [
      b?.brand ?? '',
      b?.model ?? '',
      b?.plate ?? '',
      '${b?.year ?? DateTime.now().year}',
      '${b?.mileage ?? 0}',
      b?.notes ?? '',
    ].map((v) => TextEditingController(text: v)).toList();
  }

  @override
  void dispose() {
    for (final controller in fields) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.bike == null ? 'เพิ่มรถของฉัน' : 'แก้ไขข้อมูลรถ'),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var i = 0; i < fields.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: TextFormField(
                    controller: fields[i],
                    enabled: !saving,
                    keyboardType: i == 3 || i == 4
                        ? TextInputType.number
                        : TextInputType.text,
                    maxLength: [100, 100, 30, 4, 9, 2000][i],
                    decoration: InputDecoration(
                      labelText: [
                        'ยี่ห้อ',
                        'รุ่น',
                        'ทะเบียน',
                        'ปี ค.ศ.',
                        'เลขไมล์ (กม.)',
                        'หมายเหตุ',
                      ][i],
                      counterText: '',
                    ),
                    validator: (value) {
                      if (i != 5 && (value == null || value.trim().isEmpty)) {
                        return 'กรุณากรอกข้อมูล';
                      }
                      if (i == 3 || i == 4) {
                        final number = int.tryParse(value ?? '');
                        if (number == null || number < 0) {
                          return 'กรอกจำนวนเต็มที่ไม่ติดลบ';
                        }
                        if (i == 3 && (number < 1900 || number > 2100)) {
                          return 'ปีต้องอยู่ระหว่าง 1900–2100';
                        }
                      }
                      return null;
                    },
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
      ),
    ),
    actions: [
      TextButton(
        onPressed: saving ? null : () => Navigator.pop(context),
        child: const Text('ยกเลิก'),
      ),
      FilledButton(
        onPressed: saving
            ? null
            : () async {
                if (!form.currentState!.validate()) return;
                setState(() {
                  saving = true;
                  error = null;
                });
                final ok = await widget.vm.save({
                  'brand': fields[0].text.trim(),
                  'model': fields[1].text.trim(),
                  'license_plate': fields[2].text.trim(),
                  'year': int.parse(fields[3].text),
                  'mileage': int.parse(fields[4].text),
                  'notes': fields[5].text.trim(),
                }, id: widget.bike?.id);
                if (!context.mounted) return;
                if (ok) {
                  Navigator.pop(context);
                } else {
                  setState(() {
                    saving = false;
                    error = widget.vm.error;
                  });
                }
              },
        child: Text(saving ? 'กำลังบันทึก…' : 'บันทึก'),
      ),
    ],
  );
}
