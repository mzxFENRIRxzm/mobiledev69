import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';
import 'admin_management.dart';

class AdminDatabaseTab extends StatefulWidget {
  const AdminDatabaseTab({super.key, required this.api, required this.openRecord});
  final ApiService api;
  final Future<void> Function(String table, Map<String, dynamic> row) openRecord;

  @override
  State<AdminDatabaseTab> createState() => _AdminDatabaseTabState();
}

class _AdminDatabaseTabState extends State<AdminDatabaseTab> {
  List<Map<String, dynamic>> tables = [];
  Map<String, dynamic>? pageData;
  String? table, error;
  int page = 1;
  bool loading = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => loadTables());
  }

  Future<void> loadTables() async {
    if (!mounted) return;
    setState(() { loading = true; error = null; });
    try {
      final results = (await widget.api.request('admin/database/') as List)
          .map((row) => Map<String, dynamic>.from(row as Map)).toList();
      if (!mounted) return;
      setState(() => tables = results);
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> loadPage(String selected, int nextPage) async {
    setState(() { loading = true; error = null; table = selected; page = nextPage;
      pageData = null; });
    try {
      final result = Map<String, dynamic>.from(await widget.api.request(
        'admin/database/${Uri.encodeComponent(selected)}/?page=$nextPage') as Map);
      if (mounted) setState(() => pageData = result);
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> manageRow(Map<String, dynamic> row) async {
    final category = pageData?['actions'] as String?;
    String? action;
    if (category == 'conversation' || category == 'ai_conversation') {
      action = row['archived_at'] == null ? 'archive' : 'restore';
    } else if (category == 'message' && row['redacted_at'] == null) {
      action = 'redact';
    } else if (category == 'notification') {
      action = row['hidden_at'] == null ? 'hide' : 'restore';
    } else if (category == 'knowledge_chunk') {
      action = row['is_active'] == true ? 'disable' : 'enable';
    } else if (category == 'oidc_token') {
      action = 'revoke';
    }
    if (action == null || table == null || row['id'] == null) return;
    final reason = TextEditingController();
    final needsReason = !['restore', 'enable'].contains(action);
    final confirmed = await showDialog<bool>(context: context,
      builder: (dialog) => AlertDialog(
        title: Text('ดำเนินการ $action · ${row['id']}'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          if (action == 'redact') const Text('ข้อความเดิมจะถูกเก็บในฐานข้อมูล แต่ผู้ใช้จะเห็นข้อความแทน'),
          if (action == 'revoke') const Text('โทเค็นนี้จะถูกเพิกถอนทันที ผู้ใช้ที่ใช้งานอยู่จะต้องเข้าสู่ระบบใหม่'),
          if (needsReason) TextField(controller: reason,
            decoration: const InputDecoration(labelText: 'เหตุผล (จำเป็น)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true),
            child: const Text('ยืนยัน')),
        ]));
    try {
      if (confirmed != true) return;
      if (needsReason && reason.text.trim().isEmpty) {
        throw StateError('กรุณาระบุเหตุผล');
      }
      await widget.api.request('admin/database/$table/${row['id']}/action/',
        method: 'POST', data: {'action': action, 'reason': reason.text.trim()});
      if (mounted) await loadPage(table!, page);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(adminError(e))));
      }
    } finally {
      reason.dispose();
    }
  }

  Future<void> editRow(Map<String, dynamic> row) async {
    final isKnowledge = pageData?['actions'] == 'knowledge_chunk';
    final names = isKnowledge
        ? ['title', 'source_url', 'locator', 'content', 'keywords']
        : ['title'];
    final fields = <String, TextEditingController>{
      for (final name in names) name: TextEditingController(text:
        name == 'keywords' && row[name] is List
            ? (row[name] as List).join(', ') : '${row[name] ?? ''}'),
    };
    final saved = await showDialog<bool>(context: context,
      builder: (dialog) => AlertDialog(
        title: Text('แก้ไข ${row['id']}'),
        content: SizedBox(width: 540, child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            for (final name in names) TextField(controller: fields[name],
              maxLines: name == 'content' ? 5 : 1,
              decoration: InputDecoration(labelText: name)),
            if (isKnowledge) const Text('เมื่อแก้ข้อมูลความรู้ ระบบจะปิดใช้งานจนตรวจทานใหม่'),
          ]))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก')),
          FilledButton(onPressed: () => Navigator.pop(dialog, true),
            child: const Text('บันทึก')),
        ]));
    try {
      if (saved != true || table == null) return;
      final payload = <String, dynamic>{
        for (final name in names) name: name == 'keywords'
          ? fields[name]!.text.split(',').map((item) => item.trim())
              .where((item) => item.isNotEmpty).toList()
          : fields[name]!.text.trim(),
      };
      await widget.api.request('admin/database/$table/${row['id']}/',
        method: 'PATCH', data: payload);
      if (mounted) await loadPage(table!, page);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(adminError(e))));
      }
    } finally {
      for (final field in fields.values) { field.dispose(); }
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = (pageData?['rows'] as List? ?? [])
        .map((item) => Map<String, dynamic>.from(item as Map)).toList();
    final action = pageData?['actions'] as String?;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Row(children: [
        const Expanded(child: Text('ข้อมูลฐานข้อมูล THE_X', style: TextStyle(fontSize: 20,
          fontWeight: FontWeight.bold))),
        IconButton(onPressed: table == null ? loadTables : () => loadPage(table!, page),
          icon: const Icon(Icons.refresh), tooltip: 'โหลดข้อมูลใหม่'),
      ]),
      const SizedBox(height: 6),
      const Text('แสดงตารางฐานข้อมูลแอปทั้งหมด หน้าละ 30 แถว · ค่ารหัสผ่าน โทเค็น และคีย์ถูกปิดบัง'),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(initialValue: table,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'เลือกตาราง'),
        items: [for (final item in tables) DropdownMenuItem<String>(
          value: item['table'] as String,
          child: Text('${item['table']} · ${item['model'] ?? 'ตารางระบบ'}',
            overflow: TextOverflow.ellipsis))],
        onChanged: (value) { if (value != null) loadPage(value, 1); }),
      if (loading) const LinearProgressIndicator(),
      if (error != null) Padding(padding: const EdgeInsets.all(12),
        child: Text(error!, style: const TextStyle(color: Colors.redAccent))),
      if (table != null) ...[
        const SizedBox(height: 10),
        Text('${pageData?['model'] ?? table} · หน้า $page'),
        for (final row in rows) Card(child: ExpansionTile(
          title: Text('${row['id'] ?? row.values.take(1).join()}'),
          subtitle: Text(row.entries.where((entry) =>
            ['name', 'username', 'title', 'status', 'model'].contains(entry.key))
            .map((entry) => '${entry.key}: ${entry.value}').join(' · '),
            maxLines: 2, overflow: TextOverflow.ellipsis),
          children: [Padding(padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              for (final entry in row.entries) Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: SelectableText('${entry.key}: ${entry.value ?? '—'}')),
              if (action != null && row['id'] != null)
                Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(
                  onPressed: () => ['conversation', 'message', 'ai_conversation',
                      'notification', 'knowledge_chunk', 'oidc_token'].contains(action)
                    ? manageRow(row) : widget.openRecord(table!, row),
                  icon: const Icon(Icons.open_in_new),
                  label: Text(['conversation', 'message', 'ai_conversation',
                    'notification', 'knowledge_chunk', 'oidc_token'].contains(action)
                    ? 'จัดการสถานะ' : 'เปิดเครื่องมือจัดการ'))),
              if (['ai_conversation', 'knowledge_chunk'].contains(action))
                Align(alignment: Alignment.centerRight, child: TextButton.icon(
                  onPressed: () => editRow(row),
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('แก้ไขข้อมูล'))),
            ]))],
        )),
        if (rows.isEmpty && !loading) const Padding(padding: EdgeInsets.all(16),
          child: Text('ไม่มีข้อมูลในหน้านี้')),
        Row(children: [
          TextButton(onPressed: page > 1 && !loading
            ? () => loadPage(table!, page - 1) : null,
            child: const Text('ก่อนหน้า')),
          TextButton(onPressed: pageData?['has_more'] == true && !loading
            ? () => loadPage(table!, page + 1) : null,
            child: const Text('ถัดไป')),
        ]),
      ],
    ]);
  }
}
