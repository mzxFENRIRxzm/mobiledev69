import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api/api_service.dart';
import '../../core/ui/app_theme.dart';
import 'app_menu.dart';
import 'auth_view_model.dart';
import 'admin_management.dart';
import 'admin_booking_dialog.dart';
import 'admin_database_tab.dart';
import 'admin_vector_knowledge.dart';
import 'admin_knowledge_documents.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});
  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  bool loading = true;
  String? error;
  Map<String, dynamic> overview = {};
  List<Map<String, dynamic>> users = [], shops = [], bookings = [], knowledge = [], audit = [];
  int knowledgePage = 1, knowledgeCount = 0;
  bool knowledgeHasMore = false;
  String userSearch = '', shopSearch = '', bookingSearch = '';
  ApiService get api => context.read<ApiService>();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (loading && overview.isEmpty && error == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted) load(); });
    }
  }

  List<Map<String, dynamic>> rows(dynamic value) =>
      (value as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();

  Future<void> load() async {
    setState(() { loading = true; error = null; });
    try {
      final data = await Future.wait([
        api.request('admin/overview/'),
        api.request('admin/users/?q=${Uri.encodeQueryComponent(userSearch)}'),
        api.request('admin/shops/?q=${Uri.encodeQueryComponent(shopSearch)}'),
        api.request('admin/bookings/?q=${Uri.encodeQueryComponent(bookingSearch)}'),
        api.request('admin/knowledge/'), api.request('admin/audit/'),
      ]);
      if (!mounted) return;
      setState(() {
        overview = Map<String, dynamic>.from(data[0] as Map);
        users = rows(data[1]); shops = rows(data[2]);
        bookings = rows(data[3]);
        final knowledgePageData = Map<String, dynamic>.from(data[4] as Map);
        knowledge = rows(knowledgePageData['results']);
        knowledgePage = 1;
        knowledgeCount = knowledgePageData['count'] as int;
        knowledgeHasMore = knowledgePageData['has_more'] as bool;
        audit = rows(data[5]);
      });
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> loadKnowledgePage(int page) async {
    try {
      final data = Map<String, dynamic>.from(
        await api.request('admin/knowledge/?page=$page') as Map);
      if (!mounted) return;
      setState(() {
        knowledge = rows(data['results']);
        knowledgePage = page;
        knowledgeCount = data['count'] as int;
        knowledgeHasMore = data['has_more'] as bool;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(describeError(e))));
      }
    }
  }

  Future<void> perform(Future<dynamic> Function() action, String success) async {
    try {
      await action();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(success)));
      await load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(adminError(e))));
      }
    }
  }

  Future<void> performEdit(Future<bool> Function() action, String success) async {
    try {
      if (!await action() || !mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(success)));
      await load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(adminError(e))));
      }
    }
  }

  Future<void> manageUser(Map<String, dynamic> user) => performEdit(
    () => editAdminUser(context, api, user), 'บันทึกข้อมูลผู้ใช้แล้ว');

  Future<void> manageMotorcycles(Map<String, dynamic> user) => performEdit(
    () => editAdminMotorcycles(context, api, user), 'บันทึกข้อมูลรถแล้ว');

  Future<void> manageShop(Map<String, dynamic> shop) => performEdit(
    () => editAdminShop(context, api, shop), 'บันทึกข้อมูลร้านแล้ว');

  Future<void> manageShopStatus(Map<String, dynamic> shop) => performEdit(
    () => moderateAdminShop(context, api, shop), 'เปลี่ยนสถานะร้านแล้ว');

  Future<void> openDatabaseRecord(String table, Map<String, dynamic> row) async {
    final id = row['id'] as int;
    try {
      if (table == 'auth_user') {
        final user = Map<String, dynamic>.from(
          await api.request('admin/users/$id/') as Map);
        if (mounted) await manageUser(user);
      } else if (table == 'garage_shop') {
        final shop = Map<String, dynamic>.from(
          await api.request('admin/shops/$id/details/') as Map);
        if (mounted && shop['moderation_status'] == 'deleted') {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('ร้านที่ซ่อนถาวรอ่านข้อมูลได้ แต่แก้ไขไม่ได้')));
        } else if (mounted) {
          await manageShop(shop);
        }
      } else if (table == 'garage_booking') {
        if (mounted) await showAdminBooking(context, api, id, onChanged: load);
      } else if (table == 'garage_motorcycle') {
        final owner = Map<String, dynamic>.from(
          await api.request('admin/users/${row['owner_id']}/') as Map);
        if (mounted) await manageMotorcycles(owner);
      } else if (table == 'garage_motorcycleknowledge') {
        if (mounted) await editKnowledge(row);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(adminError(e))));
      }
    }
  }

  Future<void> editUser(Map<String, dynamic> user) async {
    var role = user['role'] as String;
    var active = user['is_active'] as bool;
    final saved = await showDialog<bool>(context: context, builder: (dialog) =>
      StatefulBuilder(builder: (context, update) => AlertDialog(
        title: Text('ผู้ใช้ ${user['username']}'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          DropdownButtonFormField<String>(
            initialValue: role, decoration: const InputDecoration(labelText: 'บทบาท'),
            items: const [
              DropdownMenuItem(value: 'customer', child: Text('สมาชิกทั่วไป')),
              DropdownMenuItem(value: 'mechanic', child: Text('ผู้ให้บริการ')),
              DropdownMenuItem(value: 'admin', child: Text('Admin')),
            ],
            onChanged: (value) { if (value != null) update(() => role = value); },
          ),
          SwitchListTile(title: const Text('บัญชีใช้งานได้'), value: active,
            onChanged: (value) => update(() => active = value)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('บันทึก')),
        ],
      )));
    if (saved == true) {
      await perform(() => api.request('admin/users/${user['id']}/', method: 'PATCH',
        data: {'role': role, 'is_active': active}), 'บันทึกบทบาทแล้ว');
    }
  }

  Future<void> editShopMechanics(Map<String, dynamic> shop) async {
    List<Map<String, dynamic>> available;
    try {
      available = rows(await api.request('admin/mechanics/'));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(describeError(e))));
      }
      return;
    }
    if (!mounted) return;
    final validIds = available.map((u) => u['id'] as int).toSet();
    final selected = Set<int>.from((shop['mechanic_ids'] as List).cast<int>())
      ..retainAll(validIds);
    final saved = await showDialog<bool>(context: context, builder: (dialog) =>
      StatefulBuilder(builder: (context, update) => AlertDialog(
        title: Text('ช่างของร้าน ${shop['name']}'),
        content: SizedBox(width: 440, height: 360, child: available.isEmpty
          ? const Center(child: Text('ยังไม่มีผู้ใช้บทบาทช่างที่ใช้งานอยู่'))
          : ListView(children: [
              for (final user in available) CheckboxListTile(
                title: Text('${user['username']}'),
                value: selected.contains(user['id']),
                onChanged: (value) => update(() {
                  if (value == true) { selected.add(user['id'] as int); }
                  else { selected.remove(user['id']); }
                }),
              ),
            ])),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('บันทึก')),
        ],
      )));
    if (saved == true) {
      await perform(() => api.request('admin/shops/${shop['id']}/', method: 'PATCH',
        data: {'mechanic_ids': selected.toList()..sort()}), 'บันทึกช่างประจำร้านแล้ว');
    }
  }

  Widget input(TextEditingController controller, String label, {int lines = 1}) =>
    TextFormField(controller: controller, maxLines: lines,
      decoration: InputDecoration(labelText: label),
      validator: (value) => value == null || value.trim().isEmpty ? 'กรุณากรอก $label' : null);

  Future<void> editKnowledge([Map<String, dynamic>? existing]) async {
    final brand = TextEditingController(), model = TextEditingController(),
      year = TextEditingController(), section = TextEditingController(),
      content = TextEditingController(), source = TextEditingController();
    brand.text = '${existing?['brand'] ?? ''}';
    model.text = '${existing?['model'] ?? ''}';
    year.text = '${existing?['year'] ?? ''}';
    section.text = '${existing?['section'] ?? ''}';
    content.text = '${existing?['content'] ?? ''}';
    source.text = '${existing?['source_url'] ?? ''}';
    var reviewed = existing?['reviewed'] == true;
    final form = GlobalKey<FormState>();
    final saved = await showDialog<bool>(context: context, builder: (dialog) =>
      StatefulBuilder(builder: (context, update) => AlertDialog(
        title: Text(existing == null ? 'เพิ่มข้อมูลรถสำหรับ AI' : 'แก้ไขข้อมูลรถสำหรับ AI'),
        content: SizedBox(width: 540, child: SingleChildScrollView(child: Form(
          key: form, child: Column(mainAxisSize: MainAxisSize.min, children: [
            input(brand, 'ยี่ห้อ'), input(model, 'รุ่น'),
            TextFormField(controller: year, keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'ปี (เว้นว่างได้)'),
              validator: (v) => v!.isEmpty || (int.tryParse(v) != null &&
                int.parse(v) >= 1900 && int.parse(v) <= 2100) ? null : 'ปีไม่ถูกต้อง'),
            input(section, 'หัวข้อ เช่น เครื่องยนต์'),
            input(content, 'ข้อมูลสเปกที่ตรวจแล้ว', lines: 5),
            input(source, 'URL แหล่งข้อมูล HTTPS'),
            CheckboxListTile(value: reviewed,
              title: const Text('ตรวจความถูกต้องและสิทธิ์ใช้ข้อมูลแล้ว'),
              onChanged: (v) => update(() => reviewed = v ?? false)),
          ]),
        ))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
          FilledButton(onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(dialog, true);
          }, child: Text(existing == null ? 'เพิ่มข้อมูล' : 'บันทึกการแก้ไข')),
        ],
      )));
    if (saved == true) {
      await perform(() => api.request(
        existing == null ? 'admin/knowledge/' : 'admin/knowledge/${existing['id']}/',
        method: existing == null ? 'POST' : 'PATCH', data: {
        'brand': brand.text.trim(), 'model': model.text.trim(),
        'year': year.text.trim().isEmpty ? null : int.parse(year.text.trim()),
        'section': section.text.trim(), 'content': content.text.trim(),
        'source_url': source.text.trim(), 'reviewed': reviewed,
      }), existing == null ? 'เพิ่มข้อมูลรถแล้ว' : 'แก้ไขข้อมูลแล้ว กรุณาทำ embedding ใหม่');
    }
    for (final c in [brand, model, year, section, content, source]) { c.dispose(); }
  }

  Future<void> archiveKnowledge(Map<String, dynamic> row) async {
    final reason = TextEditingController();
    final form = GlobalKey<FormState>();
    final confirmed = await showDialog<bool>(context: context, builder: (dialog) =>
      AlertDialog(title: const Text('ลบข้อมูลนี้ออกจาก AI?'),
        content: SizedBox(width: 460, child: Form(key: form,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('${row['brand']} ${row['model']} · ${row['section']}'),
            const SizedBox(height: 8),
            const Text('ข้อมูลจะถูกซ่อน แต่ยังเก็บประวัติไว้'),
            TextFormField(controller: reason,
              decoration: const InputDecoration(labelText: 'เหตุผล'),
              validator: (value) => value != null && value.trim().length >= 3
                ? null : 'กรุณาระบุเหตุผลอย่างน้อย 3 ตัวอักษร'),
          ]))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก')),
          FilledButton(onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(dialog, true);
          }, child: const Text('ลบจาก AI')),
        ]));
    if (confirmed == true) {
      await perform(() => api.request('admin/knowledge/${row['id']}/',
        method: 'DELETE', data: {'reason': reason.text.trim()}),
        'ลบข้อมูลออกจาก AI แล้ว');
    }
    reason.dispose();
  }

  Future<void> setKey() async {
    final controller = TextEditingController();
    var visible = false;
    var hasValue = false;
    final saved = await showDialog<bool>(context: context, builder: (dialog) =>
      StatefulBuilder(builder: (context, update) => AlertDialog(
      title: const Text('ตั้งค่า Gemini Embedding API key'),
      content: SizedBox(width: 480, child: TextField(
        controller: controller, obscureText: !visible,
        onChanged: (value) => update(() => hasValue = value.trim().isNotEmpty),
        decoration: const InputDecoration(labelText: 'API key',
          helperText: 'จัดเก็บเข้ารหัสบน server และไม่แสดงค่าเดิม').copyWith(
          suffixIcon: IconButton(
            tooltip: visible ? 'ซ่อน API key' : 'แสดง API key',
            onPressed: () => update(() => visible = !visible),
            icon: Icon(visible ? Icons.visibility_off_outlined : Icons.visibility_outlined),
          )))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('ยกเลิก')),
        FilledButton(onPressed: hasValue ? () => Navigator.pop(dialog, true) : null,
          child: const Text('บันทึก')),
      ],
    )));
    if (saved == true && controller.text.trim().isNotEmpty) {
      await perform(() => api.request('admin/embedding-key/', method: 'PUT',
        data: {'api_key': controller.text.trim()}), 'บันทึก API key แล้ว');
    }
    controller.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return DefaultTabController(length: 7, child: Scaffold(
      appBar: const TheXAppBar(title: 'จัดการระบบ'),
      body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1180),
        child: Padding(padding: const EdgeInsets.all(20), child: Column(children: [
          Row(children: [
            Expanded(child: Text('Admin · ${auth.username}',
              style: Theme.of(context).textTheme.headlineMedium)),
            IconButton(onPressed: loading ? null : load,
              tooltip: 'โหลดใหม่', icon: const Icon(Icons.refresh)),
          ]),
          if (loading) const LinearProgressIndicator(),
          if (error != null) Padding(padding: const EdgeInsets.all(12),
            child: Text(error!, style: const TextStyle(color: AppColors.red))),
          const TabBar(isScrollable: true, tabs: [
            Tab(text: 'ภาพรวม'), Tab(text: 'ผู้ใช้'), Tab(text: 'ร้านบริการ'),
            Tab(text: 'การจอง'), Tab(text: 'ฐานความรู้ AI'),
            Tab(text: 'กิจกรรม Admin'), Tab(text: 'ฐานข้อมูล'),
          ]),
          Expanded(child: TabBarView(children: [
            overviewTab(), usersTab(), shopsTab(), bookingsTab(), knowledgeTab(), auditTab(),
            AdminDatabaseTab(api: api, openRecord: openDatabaseRecord),
          ])),
        ]))),
      ),
    ));
  }

  Widget overviewTab() => ListView(padding: const EdgeInsets.symmetric(vertical: 18),
    children: [
      Text('ดูแล THE_X จากที่เดียว', style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 12),
      Wrap(spacing: 12, runSpacing: 12, children: [
        metric('ผู้ใช้', overview['users']), metric('ร้าน', overview['shops']),
        metric('การจองที่ดำเนินอยู่', overview['active_bookings']),
        metric('ข้อมูลที่ Admin เพิ่ม', overview['knowledge']), metric('ทำ embedding แล้ว', overview['embedded']),
      ]),
      const SizedBox(height: 18),
      const Text('ข้อมูลรถที่ Admin เพิ่มจะค้นหาได้ผ่าน RAG หลังตรวจทานและกดทำ embedding'),
    ]);

  Widget metric(String label, dynamic value) => SizedBox(width: 200, child: Card(
    child: Padding(padding: const EdgeInsets.all(18), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(color: AppColors.muted)),
        const SizedBox(height: 8),
        Text('${value ?? '—'}', style: Theme.of(context).textTheme.headlineMedium),
      ]),
    )),
  );

  Widget usersTab() => ListView(children: [
    Padding(padding: const EdgeInsets.all(16), child: TextField(
      decoration: const InputDecoration(labelText: 'ค้นหาผู้ใช้ ชื่อ อีเมล หรือเบอร์โทร',
        prefixIcon: Icon(Icons.search), helperText: 'กด Enter เพื่อค้นหา'),
      onSubmitted: (value) { userSearch = value.trim(); load(); })),
    for (final user in users) Card(child: ListTile(
      leading: const Icon(Icons.person_outline), title: Text('${user['username']}'),
      subtitle: Text('${user['role']} · ${user['is_active'] == true ? 'ใช้งาน' : 'ปิดใช้งาน'}'),
      trailing: PopupMenuButton<String>(tooltip: 'จัดการผู้ใช้',
        onSelected: (value) => value == 'account'
          ? manageUser(user) : manageMotorcycles(user),
        itemBuilder: (_) => const [
          PopupMenuItem(value: 'account', child: Text('ข้อมูลบัญชีและบทบาท')),
          PopupMenuItem(value: 'motorcycles', child: Text('รถในโรงรถ')),
        ]),
      onTap: () => manageUser(user))),
  ]);

  Widget shopsTab() => ListView(children: [
    Padding(padding: const EdgeInsets.all(16), child: TextField(
      decoration: const InputDecoration(labelText: 'ค้นหาร้าน ชื่อ ที่อยู่ หรือโทรศัพท์',
        prefixIcon: Icon(Icons.search), helperText: 'กด Enter เพื่อค้นหา'),
      onSubmitted: (value) { shopSearch = value.trim(); load(); })),
    for (final shop in shops) Card(child: ListTile(
      leading: const Icon(Icons.storefront_outlined), title: Text('${shop['name']}'),
      subtitle: Text('${shop['address']} · ช่าง ${shop['mechanic_count']} คน · '
        '${shop['moderation_status'] == 'deleted' ? 'ซ่อนถาวร' : shop['moderation_status'] == 'banned' ? 'แบน' : shop['moderation_status'] == 'suspended' && shop['available'] == false ? 'ระงับชั่วคราว' : shop['accepting_bookings'] == true ? 'รับจอง' : 'ปิดรับจอง'}'),
      trailing: PopupMenuButton<String>(tooltip: 'จัดการร้าน',
        onSelected: (value) {
          if (value == 'details') manageShop(shop);
          if (value == 'mechanics') editShopMechanics(shop);
          if (value == 'status') manageShopStatus(shop);
        },
        itemBuilder: (_) => [
          if (shop['moderation_status'] != 'deleted') ...const [
            PopupMenuItem(value: 'details', child: Text('แก้ไขข้อมูลและหมุดร้าน')),
            PopupMenuItem(value: 'mechanics', child: Text('ช่างประจำร้าน')),
            PopupMenuItem(value: 'status', child: Text('ระงับ แบน หรือซ่อนถาวร')),
          ],
        ]),
      onTap: () => shop['moderation_status'] == 'deleted' ? null : manageShop(shop))),
  ]);

  Widget bookingsTab() => ListView(children: [
    Padding(padding: const EdgeInsets.all(16), child: TextField(
      decoration: const InputDecoration(labelText: 'ค้นหาหมายเลขจอง ลูกค้า ร้าน รถ หรือสถานะ',
        prefixIcon: Icon(Icons.search), helperText: 'กด Enter เพื่อค้นหา'),
      onSubmitted: (value) { bookingSearch = value.trim(); load(); })),
    for (final booking in bookings) Card(child: ListTile(
      leading: const Icon(Icons.event_note_outlined),
      title: Text('#${booking['id']} · ${booking['shop']}'),
      subtitle: Text('${booking['customer']} · ${booking['motorcycle']}'),
      trailing: Text(booking['archived_at'] == null
        ? bookingStatusLabel(booking['status']) : 'ซ่อนจากแอป'),
      onTap: () async {
        try {
          await showAdminBooking(context, api, booking['id'] as int,
            onChanged: load);
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(describeError(e))));
          }
        }
      })),
  ]);

  Widget knowledgeTab() {
    final key = overview['embedding_key'] as Map?;
    return ListView(children: [
      Padding(padding: const EdgeInsets.all(12), child: Text(
        'ข้อมูลที่ Admin เพิ่มเอง', style: Theme.of(context).textTheme.titleLarge)),
      Padding(padding: const EdgeInsets.all(12), child: Wrap(spacing: 10, children: [
        FilledButton.icon(onPressed: () => editKnowledge(), icon: const Icon(Icons.add),
          label: const Text('เพิ่มข้อมูลรถ')),
        OutlinedButton.icon(onPressed: setKey, icon: const Icon(Icons.key_outlined),
          label: Text(key?['configured'] == true
            ? 'เปลี่ยน API key (••••${key?['hint']})' : 'เพิ่ม API key')),
      ])),
      const Divider(height: 32),
      AdminKnowledgeDocuments(api: api),
      const Divider(height: 32),
      AdminVectorKnowledge(api: api),
      const Divider(height: 32),
      Padding(padding: const EdgeInsets.all(12), child: Text(
        'รายการข้อมูลที่ Admin เพิ่มเอง', style: Theme.of(context).textTheme.titleLarge)),
      for (final row in knowledge) Card(child: Padding(padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${row['brand']} ${row['model']} · ${row['year'] ?? 'ไม่ระบุปี'}',
            style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text('${row['section']} · ${row['embedding_status'] == 'ready' ? 'พร้อมค้นหา' : 'ยังไม่ได้ทำ embedding'}'),
          const SizedBox(height: 8),
          Text('${row['content']}', maxLines: 3, overflow: TextOverflow.ellipsis),
          Text('${row['source_url']}', maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.muted)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            OutlinedButton.icon(onPressed: () => editKnowledge(row),
              icon: const Icon(Icons.edit_outlined), label: const Text('แก้ไข')),
            OutlinedButton.icon(onPressed: () => archiveKnowledge(row),
              icon: const Icon(Icons.delete_outline), label: const Text('ลบจาก AI')),
            if (row['reviewed'] == true) OutlinedButton.icon(
              onPressed: () => perform(() => api.request('admin/knowledge/${row['id']}/embed/',
                method: 'POST'), 'ทำ embedding แล้ว'),
              icon: const Icon(Icons.auto_awesome_outlined), label: const Text('ทำ embedding')),
            if (row['reviewed'] != true) OutlinedButton(
              onPressed: () => perform(() => api.request('admin/knowledge/${row['id']}/',
                method: 'PATCH', data: {'reviewed': true}), 'ตรวจทานแล้ว'),
              child: const Text('ยืนยันว่าตรวจข้อมูลแล้ว')),
          ]),
        ]),
      )),
      if (knowledgeCount > 20) Padding(padding: const EdgeInsets.all(12), child: Row(
        mainAxisAlignment: MainAxisAlignment.center, children: [
          IconButton(onPressed: knowledgePage <= 1 ? null
            : () => loadKnowledgePage(knowledgePage - 1),
            icon: const Icon(Icons.chevron_left), tooltip: 'หน้าก่อน'),
          Text('หน้า $knowledgePage / ${(knowledgeCount + 19) ~/ 20}'),
          IconButton(onPressed: !knowledgeHasMore ? null
            : () => loadKnowledgePage(knowledgePage + 1),
            icon: const Icon(Icons.chevron_right), tooltip: 'หน้าถัดไป'),
        ],
      )),
    ]);
  }

  Widget auditTab() => ListView(children: [
    const Padding(padding: EdgeInsets.all(16), child: Text('กิจกรรมจัดการระบบล่าสุด · 100 รายการ')),
    for (final event in audit) Card(child: ListTile(
      leading: const Icon(Icons.history_outlined),
      title: Text('${event['actor']} · ${event['action']}'),
      subtitle: Text('${event['target_type']} #${event['target_id'] ?? '—'} · ${event['created_at']}'),
    )),
  ]);
}
