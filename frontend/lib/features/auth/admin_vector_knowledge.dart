import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';
import '../../core/ui/app_theme.dart';

/// Passages searched by n8n's PGVector Store, including imported Honda data.
class AdminVectorKnowledge extends StatefulWidget {
  final ApiService api;
  const AdminVectorKnowledge({super.key, required this.api});

  @override
  State<AdminVectorKnowledge> createState() => _AdminVectorKnowledgeState();
}

class _AdminVectorKnowledgeState extends State<AdminVectorKnowledge> {
  final search = TextEditingController();
  List<Map<String, dynamic>> results = [];
  int page = 1, count = 0;
  bool hasMore = false, busy = true;
  String? error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => load());
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> load({int nextPage = 1}) async {
    if (!mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final data = Map<String, dynamic>.from(
        await widget.api.request(
              'admin/ai-vectors/?page=$nextPage&q=${Uri.encodeQueryComponent(search.text.trim())}',
            )
            as Map,
      );
      if (!mounted) return;
      setState(() {
        results = (data['results'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList();
        page = nextPage;
        count = data['count'] as int;
        hasMore = data['has_more'] as bool;
      });
    } catch (exception) {
      if (mounted) setState(() => error = describeError(exception));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> edit(Map<String, dynamic> row) async {
    final metadata = Map<String, dynamic>.from(row['metadata'] as Map);
    final content = TextEditingController(text: '${row['content']}');
    final title = TextEditingController(text: '${metadata['title'] ?? ''}');
    final model = TextEditingController(text: '${metadata['model'] ?? ''}');
    final year = TextEditingController(text: '${metadata['year'] ?? ''}');
    final section = TextEditingController(text: '${metadata['section'] ?? ''}');
    final source = TextEditingController(
      text: '${metadata['source_url'] ?? ''}',
    );
    final form = GlobalKey<FormState>();
    final saved = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('แก้ไขข้อมูลที่ AI ค้นหา'),
        content: SizedBox(
          width: 590,
          child: SingleChildScrollView(
            child: Form(
              key: form,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  field(title, 'ชื่อรายการ', 250),
                  field(model, 'รุ่นรถ', 160),
                  TextFormField(
                    controller: year,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'ปี (เว้นว่างได้)',
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) return null;
                      final number = int.tryParse(value.trim());
                      return number != null && number >= 1900 && number <= 2100
                          ? null
                          : 'ปีไม่ถูกต้อง';
                    },
                  ),
                  field(section, 'หัวข้อ', 120),
                  field(content, 'เนื้อหาที่ AI ใช้ตอบ', 3000, lines: 8),
                  TextFormField(
                    controller: source,
                    decoration: const InputDecoration(
                      labelText: 'URL แหล่งข้อมูล HTTPS',
                    ),
                    validator: (value) =>
                        value != null && value.startsWith('https://')
                        ? null
                        : 'ต้องใช้ลิงก์ HTTPS',
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'ถ้าแก้เนื้อหา ระบบจะสร้าง embedding ใหม่ก่อนบันทึก ต้องตั้งค่า Gemini Embedding API key',
                  ),
                ],
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก'),
          ),
          FilledButton(
            onPressed: () {
              if (form.currentState!.validate()) Navigator.pop(dialog, true);
            },
            child: const Text('บันทึก'),
          ),
        ],
      ),
    );
    if (saved == true) {
      try {
        await widget.api.request(
          'admin/ai-vectors/${row['id']}/',
          method: 'PATCH',
          data: {
            'title': title.text.trim(),
            'model': model.text.trim(),
            'year': year.text.trim().isEmpty
                ? null
                : int.parse(year.text.trim()),
            'section': section.text.trim(),
            'content': content.text.trim(),
            'source_url': source.text.trim(),
          },
        );
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('บันทึกข้อมูล AI แล้ว')));
          await load(nextPage: page);
        }
      } catch (exception) {
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(describeError(exception))));
        }
      }
    }
    for (final controller in [content, title, model, year, section, source]) {
      controller.dispose();
    }
  }

  Widget field(
    TextEditingController controller,
    String label,
    int maximum, {
    int lines = 1,
  }) => TextFormField(
    controller: controller,
    maxLines: lines,
    maxLength: maximum,
    decoration: InputDecoration(labelText: label),
    validator: (value) =>
        value == null || value.trim().isEmpty ? 'กรุณากรอก $label' : null,
  );

  Future<void> remove(Map<String, dynamic> row) async {
    final reason = TextEditingController();
    final form = GlobalKey<FormState>();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('ลบข้อมูลออกจากการค้นหา AI?'),
        content: SizedBox(
          width: 460,
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${(row['metadata'] as Map)['title'] ?? row['id']}'),
                const SizedBox(height: 10),
                const Text('รายการจะถูกย้ายไปประวัติและ AI จะค้นหาไม่พบอีก'),
                TextFormField(
                  controller: reason,
                  decoration: const InputDecoration(labelText: 'เหตุผล'),
                  validator: (value) =>
                      value != null && value.trim().length >= 3
                      ? null
                      : 'กรุณาระบุเหตุผลอย่างน้อย 3 ตัวอักษร',
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('ยกเลิก'),
          ),
          FilledButton(
            onPressed: () {
              if (form.currentState!.validate()) Navigator.pop(dialog, true);
            },
            child: const Text('ลบจาก AI'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      try {
        await widget.api.request(
          'admin/ai-vectors/${row['id']}/',
          method: 'DELETE',
          data: {'reason': reason.text.trim()},
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('ลบจากการค้นหาแล้ว เก็บประวัติไว้')),
          );
          await load(nextPage: page);
        }
      } catch (exception) {
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(describeError(exception))));
        }
      }
    }
    reason.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Text(
          'ข้อมูลที่ AI ค้นหาได้จริง · $count รายการ',
          style: Theme.of(context).textTheme.titleLarge,
        ),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: TextField(
          controller: search,
          onSubmitted: (_) => load(),
          decoration: InputDecoration(
            labelText: 'ค้นหารุ่นรถหรือเนื้อหา เช่น Honda',
            prefixIcon: const Icon(Icons.search),
            suffixIcon: IconButton(
              onPressed: () => load(),
              tooltip: 'ค้นหา',
              icon: const Icon(Icons.search),
            ),
          ),
        ),
      ),
      if (busy) const LinearProgressIndicator(),
      if (error != null)
        Padding(
          padding: const EdgeInsets.all(12),
          child: Text(error!, style: const TextStyle(color: AppColors.red)),
        ),
      if (!busy && error == null && results.isEmpty)
        const Padding(
          padding: EdgeInsets.all(12),
          child: Text('ไม่พบข้อมูลที่ค้นหา'),
        ),
      for (final row in results) _card(row),
      if (count > 20)
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                onPressed: busy || page <= 1
                    ? null
                    : () => load(nextPage: page - 1),
                icon: const Icon(Icons.chevron_left),
                tooltip: 'หน้าก่อน',
              ),
              Text('หน้า $page / ${(count + 19) ~/ 20}'),
              IconButton(
                onPressed: busy || !hasMore
                    ? null
                    : () => load(nextPage: page + 1),
                icon: const Icon(Icons.chevron_right),
                tooltip: 'หน้าถัดไป',
              ),
            ],
          ),
        ),
    ],
  );

  Widget _card(Map<String, dynamic> row) {
    final metadata = Map<String, dynamic>.from(row['metadata'] as Map);
    return SizedBox(
      width: double.infinity,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${metadata['title'] ?? metadata['model'] ?? row['id']}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              Text(
                'รุ่น ${metadata['model'] ?? '—'} · ปี ${metadata['year'] ?? 'ไม่ระบุ'} · ${metadata['section'] ?? ''}',
              ),
              const SizedBox(height: 6),
              Text(
                '${row['content']}',
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 6),
              Text(
                '${metadata['source_url'] ?? ''}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppColors.muted),
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton.icon(
                    onPressed: () => showDialog<void>(
                      context: context,
                      builder: (dialog) => AlertDialog(
                        title: Text(
                          '${metadata['title'] ?? metadata['model'] ?? row['id']}',
                        ),
                        content: SizedBox(
                          width: 600,
                          child: SingleChildScrollView(
                            child: SelectableText(
                              '${row['content']}\n\n${metadata['source_url'] ?? ''}',
                            ),
                          ),
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(dialog),
                            child: const Text('ปิด'),
                          ),
                        ],
                      ),
                    ),
                    icon: const Icon(Icons.visibility_outlined),
                    label: const Text('ดูทั้งหมด'),
                  ),
                  if (metadata['knowledge_id'] == null)
                    OutlinedButton.icon(
                      onPressed: () => edit(row),
                      icon: const Icon(Icons.edit_outlined),
                      label: const Text('แก้ไข'),
                    ),
                  if (metadata['knowledge_id'] == null)
                    OutlinedButton.icon(
                      onPressed: () => remove(row),
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('ลบจาก AI'),
                    ),
                  if (metadata['knowledge_id'] != null)
                    const Text('จัดการรายการนี้ในส่วนข้อมูลที่ Admin เพิ่มเอง'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
