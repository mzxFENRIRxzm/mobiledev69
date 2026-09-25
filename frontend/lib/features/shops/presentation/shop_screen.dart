import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../auth/auth_view_model.dart';
import '../../auth/app_menu.dart';
import '../domain/shop.dart';
import 'shop_view_model.dart';

class ShopScreen extends StatelessWidget {
  const ShopScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final vm = context.watch<ShopViewModel>();
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('ร้านและศูนย์บริการ'),
        actions: [
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
          constraints: const BoxConstraints(maxWidth: 1000),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              TextField(
                onChanged: vm.search,
                decoration: const InputDecoration(
                  labelText: 'ค้นหาชื่อร้านหรือที่อยู่',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  onPressed: vm.loading || vm.busy ? null : vm.load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('โหลดใหม่'),
                ),
              ),
              if (vm.loading || vm.busy) const LinearProgressIndicator(),
              if (vm.error != null)
                Text(
                  vm.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              if (!vm.loading && vm.filtered.isEmpty)
                const Text('ไม่พบร้านที่ตรงกับคำค้น'),
              for (final shop in vm.filtered)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          shop.name,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          shop.acceptingBookings
                              ? 'เปิดรับการจอง'
                              : 'ปิดรับการจองชั่วคราว',
                        ),
                        const SizedBox(height: 8),
                        Text('ที่อยู่: ${shop.address}'),
                        if (shop.photo != null && shop.photo!.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            child: Image.network(
                              shop.photo!,
                              height: 180,
                              width: double.infinity,
                              fit: BoxFit.cover,
                              semanticLabel: 'รูปร้าน ${shop.name}',
                              errorBuilder: (_, error, stack) =>
                                  const Text('ไม่สามารถโหลดรูปร้านได้'),
                            ),
                          ),
                        Text('โทร: ${shop.phone}'),
                        if (shop.latitude != null && shop.longitude != null)
                          TextButton.icon(
                            icon: const Icon(Icons.place_outlined),
                            label: const Text('ดูตำแหน่งร้านบนแผนที่'),
                            onPressed: () async {
                              final uri =
                                  Uri.https('www.openstreetmap.org', '/', {
                                    'mlat': '${shop.latitude}',
                                    'mlon': '${shop.longitude}',
                                  }).replace(
                                    fragment:
                                        'map=17/${shop.latitude}/${shop.longitude}',
                                  );
                              final opened = await launchUrl(uri);
                              if (!opened && context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'เปิดแผนที่ไม่ได้ กรุณาลองใหม่',
                                    ),
                                  ),
                                );
                              }
                            },
                          ),
                        if (shop.description.isNotEmpty) Text(shop.description),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 12,
                          children: [
                            if (!auth.isMechanic)
                              FilledButton(
                                onPressed: shop.acceptingBookings
                                    ? () => context.go(
                                        '/bookings?shop=${shop.id}',
                                      )
                                    : null,
                                child: const Text('จองกับร้านนี้'),
                              ),
                            if (!auth.isMechanic)
                              OutlinedButton.icon(
                                onPressed: () =>
                                    context.go('/messages?shop=${shop.id}'),
                                icon: const Icon(Icons.chat_bubble_outline),
                                label: const Text('แชตร้าน'),
                              ),
                            if (shop.canManage)
                              OutlinedButton(
                                onPressed: vm.busy || vm.loading
                                    ? null
                                    : () => showDialog<void>(
                                        context: context,
                                        barrierDismissible: false,
                                        builder: (_) =>
                                            ShopForm(shop: shop, vm: vm),
                                      ),
                                child: const Text('แก้ไขข้อมูลร้าน'),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class ShopForm extends StatefulWidget {
  final Shop shop;
  final ShopViewModel vm;
  const ShopForm({super.key, required this.shop, required this.vm});
  @override
  State<ShopForm> createState() => _ShopFormState();
}

class _ShopFormState extends State<ShopForm> {
  final form = GlobalKey<FormState>();
  late final name = TextEditingController(text: widget.shop.name);
  late final address = TextEditingController(text: widget.shop.address);
  late final phone = TextEditingController(text: widget.shop.phone);
  late final description = TextEditingController(text: widget.shop.description);
  late bool accepting = widget.shop.acceptingBookings;
  bool saving = false;
  String? error;
  @override
  void dispose() {
    for (final c in [name, address, phone, description]) {
      c.dispose();
    }
    super.dispose();
  }

  Widget field(
    TextEditingController controller,
    String label,
    int limit, {
    bool required = true,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextFormField(
      controller: controller,
      enabled: !saving,
      maxLength: limit,
      decoration: InputDecoration(labelText: label),
      validator: (v) => required && (v == null || v.trim().isEmpty)
          ? 'กรุณากรอกข้อมูล'
          : null,
    ),
  );
  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !saving,
    child: AlertDialog(
      title: const Text('แก้ไขข้อมูลร้าน'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                field(name, 'ชื่อร้าน', 160),
                field(address, 'ที่อยู่', 1000),
                field(phone, 'เบอร์โทร', 30),
                field(description, 'รายละเอียดบริการ', 2000, required: false),
                SwitchListTile(
                  title: const Text('เปิดรับการจองใหม่'),
                  value: accepting,
                  onChanged: saving
                      ? null
                      : (v) => setState(() => accepting = v),
                ),
                if (error != null)
                  Text(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
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
                  final message = await widget.vm.save(widget.shop.id, {
                    'name': name.text.trim(),
                    'address': address.text.trim(),
                    'phone': phone.text.trim(),
                    'description': description.text.trim(),
                    'accepting_bookings': accepting,
                  });
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
          child: Text(saving ? 'กำลังบันทึก…' : 'บันทึก'),
        ),
      ],
    ),
  );
}
