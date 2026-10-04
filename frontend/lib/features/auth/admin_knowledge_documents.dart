import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';

class AdminKnowledgeDocuments extends StatefulWidget {
  final ApiService api;
  const AdminKnowledgeDocuments({super.key, required this.api});

  @override
  State<AdminKnowledgeDocuments> createState() => _AdminKnowledgeDocumentsState();
}

class _AdminKnowledgeDocumentsState extends State<AdminKnowledgeDocuments> {
  List<Map<String, dynamic>> documents = [];
  bool busy = false;
  String? error;
  int page = 1;
  bool hasMore = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => load());
  }

  Future<void> load([int requestedPage = 1]) async {
    if (!mounted) return;
    setState(() { busy = true; error = null; });
    try {
      final result = Map<String, dynamic>.from(await widget.api.request(
        'admin/knowledge-documents/?page=$requestedPage') as Map);
      if (!mounted) return;
      setState(() {
        documents = (result['results'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map)).toList();
        page = requestedPage;
        hasMore = result['has_more'] == true;
      });
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> upload() async {
    const types = XTypeGroup(label: 'เอกสารสำหรับ AI', extensions: [
      'pdf', 'docx', 'txt', 'md', 'csv', 'json', 'xlsx',
    ]);
    final selected = await openFile(acceptedTypeGroups: [types]);
    if (selected == null || !mounted) return;
    final title = TextEditingController(text: selected.name);
    final brand = TextEditingController();
    final model = TextEditingController();
    final year = TextEditingController();
    final source = TextEditingController();
    final form = GlobalKey<FormState>();
    final confirmed = await showDialog<bool>(context: context, builder: (dialog) =>
      AlertDialog(title: const Text('เพิ่มไฟล์ฐานความรู้ AI'),
        content: SizedBox(width: 540, child: SingleChildScrollView(child:
          Form(key: form, child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(selected.name),
            const SizedBox(height: 8),
            TextFormField(controller: title,
              decoration: const InputDecoration(labelText: 'ชื่อเอกสาร'),
              validator: (value) => value == null || value.trim().isEmpty
                ? 'กรุณาระบุชื่อเอกสาร' : null),
            TextField(controller: brand,
              decoration: const InputDecoration(labelText: 'ยี่ห้อ (ถ้ามี)')),
            TextField(controller: model,
              decoration: const InputDecoration(labelText: 'รุ่น (ถ้ามี)')),
            TextFormField(controller: year,
              decoration: const InputDecoration(labelText: 'ปี (ถ้ามี)'),
              keyboardType: TextInputType.number,
              validator: (value) => value == null || value.trim().isEmpty ||
                (int.tryParse(value.trim()) != null &&
                 int.parse(value.trim()) >= 1900 && int.parse(value.trim()) <= 2100)
                ? null : 'ปีไม่ถูกต้อง'),
            TextFormField(controller: source,
              decoration: const InputDecoration(
                labelText: 'URL แหล่งข้อมูล HTTPS (ถ้ามี)'),
              validator: (value) => value == null || value.trim().isEmpty ||
                Uri.tryParse(value.trim())?.scheme == 'https'
                ? null : 'URL ต้องใช้ HTTPS'),
            const SizedBox(height: 12),
            const Text('ระบบเก็บข้อความที่สกัด ชื่อไฟล์ และ hash โดยไม่เปิดไฟล์ต้นฉบับให้ผู้ใช้ทั่วไป อ่านและตรวจแต่ละช่วงก่อนทำ embedding'),
          ])))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก')),
          FilledButton(onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(dialog, true);
          }, child: const Text('อัปโหลดและสกัดข้อความ')),
        ]));
    if (confirmed == true) {
      try {
        final bytes = await selected.readAsBytes();
        if (bytes.isEmpty || bytes.length > 5 * 1024 * 1024) {
          throw StateError('ไฟล์ต้องมีขนาดไม่เกิน 5 MB');
        }
        final payload = FormData.fromMap({
          'file': MultipartFile.fromBytes(bytes, filename: selected.name),
          'title': title.text.trim(), 'brand': brand.text.trim(),
          'model': model.text.trim(),
          'source_url': source.text.trim(),
        });
        if (year.text.trim().isNotEmpty) {
          payload.fields.add(MapEntry('year', year.text.trim()));
        }
        await widget.api.request('admin/knowledge-documents/',
          method: 'POST', data: payload);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('สกัดข้อความแล้ว กรุณาตรวจรายละเอียดก่อนทำ embedding')));
          await load();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(e is StateError ? e.message : describeError(e))));
        }
      }
    }
    for (final item in [title, brand, model, year, source]) { item.dispose(); }
  }

  Future<void> showDocument(Map<String, dynamic> summary) async {
    Map<String, dynamic> detail;
    try {
      detail = Map<String, dynamic>.from(await widget.api.request(
        'admin/knowledge-documents/${summary['id']}/') as Map);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(describeError(e))));
      }
      return;
    }
    if (!mounted) return;
    await showDialog<void>(context: context, builder: (dialog) =>
      StatefulBuilder(builder: (context, update) {
        final sections = (detail['sections'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map)).toList();
        Future<void> reload() async {
          final data = Map<String, dynamic>.from(await widget.api.request(
            'admin/knowledge-documents/${summary['id']}/') as Map);
          update(() => detail = data);
          await load(page);
        }
        Future<void> action(Future<dynamic> Function() request) async {
          try {
            await request();
            await reload();
          } catch (e) {
            if (dialog.mounted) {
              ScaffoldMessenger.of(dialog).showSnackBar(
                SnackBar(content: Text(describeError(e))));
            }
          }
        }
        return AlertDialog(
          title: Text('${detail['title']} · ${detail['filename']}'),
          content: SizedBox(width: 820, height: 610, child: ListView(children: [
            Text('ชนิด ${detail['file_type']} · ${detail['file_size']} bytes · SHA-256 ${detail['sha256']}'),
            Text('ยี่ห้อ ${detail['brand']} · รุ่น ${detail['model']} · ปี ${detail['year'] ?? 'ไม่ระบุ'}'),
            if ('${detail['source_url']}'.isNotEmpty) Text('แหล่งข้อมูล: ${detail['source_url']}'),
            const SizedBox(height: 12),
            ExpansionTile(title: const Text('ข้อความทั้งหมดที่สกัดจากไฟล์'),
              subtitle: const Text('ใช้ตรวจความครบถ้วนของหน้า ตาราง และชีต'),
              children: [Padding(padding: const EdgeInsets.all(12), child:
                SelectableText('${detail['extracted_text']}'))]),
            const Divider(),
            Text('ช่วงข้อความ ${sections.length} รายการ · ตรวจและทำ embedding ทีละช่วง',
              style: Theme.of(context).textTheme.titleMedium),
            for (var index = 0; index < sections.length; index++)
              Card(child: Padding(padding: const EdgeInsets.all(12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${sections[index]['locator']} · ${sections[index]['embedding_status'] == 'ready' ? 'พร้อมค้นหา' : 'ยังไม่ทำ embedding'}',
                    style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  SelectableText('${sections[index]['content']}'),
                  Wrap(spacing: 8, children: [
                    OutlinedButton(onPressed: () async {
                      final editor = TextEditingController(text: '${sections[index]['content']}');
                      final saved = await showDialog<bool>(context: dialog,
                        builder: (inner) => AlertDialog(
                          title: Text('แก้ ${sections[index]['locator']}'),
                          content: SizedBox(width: 650, child: TextField(
                            controller: editor, maxLines: 12,
                            maxLength: 1400)),
                          actions: [
                            TextButton(onPressed: () => Navigator.pop(inner, false),
                              child: const Text('ยกเลิก')),
                            FilledButton(onPressed: () => Navigator.pop(inner, true),
                              child: const Text('บันทึก')),
                          ]));
                      if (saved == true && editor.text.trim().isNotEmpty) {
                        await action(() => widget.api.request(
                          'admin/knowledge-documents/${summary['id']}/sections/$index/',
                          method: 'PATCH', data: {'content': editor.text.trim()}));
                      }
                      editor.dispose();
                    }, child: const Text('แก้ข้อความ')),
                    if (sections[index]['reviewed'] != true)
                      OutlinedButton(onPressed: () => action(() => widget.api.request(
                        'admin/knowledge-documents/${summary['id']}/sections/$index/',
                        method: 'PATCH', data: {'reviewed': true})),
                        child: const Text('ตรวจแล้ว')),
                    if (sections[index]['reviewed'] == true)
                      OutlinedButton(onPressed: () => action(() => widget.api.request(
                        'admin/knowledge-documents/${summary['id']}/sections/$index/embed/',
                        method: 'POST')), child: const Text('ทำ embedding')),
                  ]),
                ]))),
          ])),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialog),
              child: const Text('ปิด')),
            TextButton(onPressed: () async {
              final confirmed = await showDialog<bool>(context: dialog,
                builder: (inner) => AlertDialog(
                  title: const Text('ซ่อนเอกสารและนำ embedding ออก?'),
                  content: const Text('เก็บประวัติในฐานข้อมูล แต่ AI จะไม่ค้นเจอข้อมูลนี้'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(inner, false),
                      child: const Text('ยกเลิก')),
                    FilledButton(onPressed: () => Navigator.pop(inner, true),
                      child: const Text('ยืนยัน')),
                  ]));
              if (confirmed != true) return;
              try {
                await widget.api.request('admin/knowledge-documents/${summary['id']}/',
                  method: 'DELETE');
                if (dialog.mounted) Navigator.pop(dialog);
                await load();
              } catch (e) {
                if (dialog.mounted) {
                  ScaffoldMessenger.of(dialog).showSnackBar(
                    SnackBar(content: Text(describeError(e))));
                }
              }
            }, child: const Text('ซ่อนเอกสาร')),
          ],
        );
      }));
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.all(12), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('เอกสารที่อัปโหลด', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          const Text('PDF, DOCX, TXT, MD, CSV, JSON, XLSX · ไม่เกิน 5 MB · PDF ภาพสแกนยังไม่รองรับ OCR'),
          const SizedBox(height: 8),
          FilledButton.icon(onPressed: busy ? null : upload,
            icon: const Icon(Icons.upload_file), label: const Text('เพิ่มไฟล์')),
        ])),
      if (busy) const LinearProgressIndicator(),
      if (error != null) Padding(padding: const EdgeInsets.all(12), child:
        Text(error!, style: const TextStyle(color: Colors.redAccent))),
      for (final row in documents) Card(child: ListTile(
        leading: const Icon(Icons.description_outlined),
        title: Text('${row['title']} · ${row['filename']}'),
        subtitle: Text('${row['section_count']} ช่วง · ตรวจแล้ว ${row['reviewed_count']} · ทำ embedding ${row['embedded_count']}'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => showDocument(row),
      )),
      if (page > 1 || hasMore) Row(mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(onPressed: page > 1 ? () => load(page - 1) : null,
            icon: const Icon(Icons.chevron_left)),
          Text('หน้า $page'),
          IconButton(onPressed: hasMore ? () => load(page + 1) : null,
            icon: const Icon(Icons.chevron_right)),
        ]),
    ]);
}
