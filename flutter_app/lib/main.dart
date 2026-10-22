import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:archive/archive.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const KenozApp());

const navy = Color(0xFF123044);
const gold = Color(0xFFBD9653);
const cream = Color(0xFFF8F7F2);
const apiRoot = 'https://api.coptic.io/api';

class KenozApp extends StatelessWidget {
  const KenozApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'كنوز',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(useMaterial3: true, scaffoldBackgroundColor: cream,
      colorScheme: ColorScheme.fromSeed(seedColor: navy, primary: navy, secondary: gold),
      appBarTheme: const AppBarTheme(backgroundColor: navy, foregroundColor: Colors.white, centerTitle: true),
      fontFamily: 'sans-serif'),
    home: const HomePage(),
  );
}

class LocalStore {
  static Future<Directory> _dir() async {
    final base = await getApplicationDocumentsDirectory();
    final d = Directory('${base.path}/kenoz_cache');
    if (!await d.exists()) await d.create(recursive: true);
    return d;
  }
  static String _safe(String key) => base64Url.encode(utf8.encode(key)).replaceAll('=', '');
  static Future<void> save(String key, String data) async {
    final d = await _dir();
    await File('${d.path}/${_safe(key)}.json').writeAsString(data, flush: true);
  }
  static Future<String?> read(String key) async {
    try {
      final d = await _dir();
      final f = File('${d.path}/${_safe(key)}.json');
      if (await f.exists()) return await f.readAsString();
    } catch (_) {}
    return null;
  }
}

class ApiResult {
  final dynamic data;
  final bool offline;
  const ApiResult(this.data, this.offline);
}

class KenozApi {
  static Future<ApiResult> get(String path, {Map<String, String>? query}) async {
    final uri = Uri.parse('$apiRoot$path').replace(queryParameters: query);
    final key = uri.toString();
    try {
      final response = await http.get(uri, headers: {'Accept':'application/json'}).timeout(const Duration(seconds: 12));
      if (response.statusCode < 200 || response.statusCode >= 300) throw HttpException('HTTP ${response.statusCode}');
      final body = utf8.decode(response.bodyBytes);
      final decoded = jsonDecode(body);
      await LocalStore.save(key, body);
      return ApiResult(decoded, false);
    } catch (_) {
      final saved = await LocalStore.read(key);
      if (saved != null) return ApiResult(jsonDecode(saved), true);
      rethrow;
    }
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override State<HomePage> createState() => _HomePageState();
}
class _HomePageState extends State<HomePage> {
  int tab = 0;
  final pages = const [DashboardPage(), BiblePage(), PrayerPage(), ChurchPage(), NotesPage()];
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('كنوز ✝'), actions: [IconButton(tooltip:'حول التطبيق',onPressed:()=>showAboutDialog(context:context,applicationName:'كنوز KENOZ',applicationVersion:'1.0.0',children:const [Text('تطبيق قبطي أرثوذكسي قيد التطوير. تُحفظ البيانات التي يتم تحميلها تلقائيًا لاستخدامها دون إنترنت.')]),icon:const Icon(Icons.info_outline))]),
    body: IndexedStack(index:tab,children:pages),
    bottomNavigationBar: NavigationBar(selectedIndex:tab,onDestinationSelected:(i)=>setState(()=>tab=i),destinations:const [
      NavigationDestination(icon:Icon(Icons.home_outlined),selectedIcon:Icon(Icons.home),label:'الرئيسية'),
      NavigationDestination(icon:Icon(Icons.menu_book_outlined),selectedIcon:Icon(Icons.menu_book),label:'الكتاب'),
      NavigationDestination(icon:Icon(Icons.auto_stories_outlined),selectedIcon:Icon(Icons.auto_stories),label:'الأجبية'),
      NavigationDestination(icon:Icon(Icons.church_outlined),selectedIcon:Icon(Icons.church),label:'الكنيسة'),
      NavigationDestination(icon:Icon(Icons.edit_note),selectedIcon:Icon(Icons.edit_note),label:'ملاحظاتي'),
    ]),
  );
}

class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});
  @override Widget build(BuildContext context) => ListView(padding:const EdgeInsets.all(18),children:[
    Container(padding:const EdgeInsets.all(22),decoration:BoxDecoration(gradient:const LinearGradient(colors:[navy,Color(0xFF20536A)]),borderRadius:BorderRadius.circular(22)),child:const Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('سلام ونعمة ✝',style:TextStyle(color:gold,fontSize:16)),SizedBox(height:8),Text('كنوز الإيمان',style:TextStyle(color:Colors.white,fontSize:27,fontWeight:FontWeight.bold)),SizedBox(height:8),Text('صلِّ، اقرأ، وتعلّم كل يوم',style:TextStyle(color:Colors.white70,fontSize:15))])),
    const SizedBox(height:18),
    const SectionCard(title:'قراءات اليوم',subtitle:'القطمارس والسنكسار والصوم والموسم الطقسي',icon:Icons.calendar_month,child:DailyReadings()),
    const SizedBox(height:12),
    const Text('مكتبة كنوز',style:TextStyle(fontSize:20,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:10),
    Wrap(spacing:10,runSpacing:10,children:[
      _shortcut(context,'الكتاب المقدس',Icons.menu_book,1),
      _shortcut(context,'الأجبية',Icons.auto_stories,2),
      _shortcut(context,'القطمارس والسنكسار',Icons.event_note,3),
      _shortcut(context,'ملاحظاتي',Icons.note_alt,4),
    ]),
    const SizedBox(height:16),
    const Text('المحتوى الذي يُحمّل بنجاح يُحفظ تلقائيًا على الجهاز. أول تحميل يحتاج اتصالًا بالإنترنت.',style:TextStyle(height:1.6,color:Colors.black54)),
  ]);
  Widget _shortcut(BuildContext c,String t,IconData i,int tab) {
    final today=DateTime.now().toIso8601String().substring(0,10);
    final path=tab==3?'/synaxarium/$today':'/readings/$today?detailed=true';
    return SizedBox(width:MediaQuery.of(c).size.width/2-24,child:Card(color:Colors.white,child:InkWell(
      borderRadius:BorderRadius.circular(14),
      onTap:()=>Navigator.of(c).push(MaterialPageRoute(builder:(_)=>DetailPage(title:t,path:path))),
      child:Padding(padding:const EdgeInsets.all(16),child:Column(children:[Icon(i,color:gold,size:30),const SizedBox(height:8),Text(t,textAlign:TextAlign.center,style:const TextStyle(fontWeight:FontWeight.bold))]))
    )));
  }
}

class SectionCard extends StatelessWidget {
  final String title,subtitle; final IconData icon; final Widget child;
  const SectionCard({super.key,required this.title,required this.subtitle,required this.icon,required this.child});
  @override Widget build(BuildContext context)=>Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(children:[Icon(icon,color:gold),const SizedBox(width:8),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(title,style:const TextStyle(fontWeight:FontWeight.bold,fontSize:17)),Text(subtitle,style:const TextStyle(color:Colors.black54,fontSize:12))]))]),const SizedBox(height:12),child])));
}

class DailyReadings extends StatelessWidget {
  const DailyReadings({super.key});
  @override Widget build(BuildContext context)=>Wrap(spacing:8,runSpacing:8,children:[
    _btn(context,'قراءات القطمارس',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'قراءات القطمارس',path:'/readings/${DateTime.now().toIso8601String().substring(0,10)}?detailed=true')))),
    _btn(context,'سنكسار اليوم',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'سنكسار اليوم',path:'/synaxarium/${DateTime.now().toIso8601String().substring(0,10)}')))),
    _btn(context,'الصوم والموسم',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'الصوم',path:'/fasting/${DateTime.now().toIso8601String().substring(0,10)}')))),
  ]);
  Widget _btn(BuildContext c,String s,VoidCallback f)=>OutlinedButton(onPressed:f,child:Text(s));
}

class BiblePage extends StatefulWidget { const BiblePage({super.key}); @override State<BiblePage> createState()=>_BiblePageState(); }
class _BiblePageState extends State<BiblePage> {
  List<dynamic> books=[]; bool loading=true; String error=''; int bookIndex=0,chapterIndex=0; String query='';
  @override void initState(){super.initState();_load();}
  Future<void> _load() async {try{final raw=await rootBundle.loadString('assets/bible-data.json');final d=jsonDecode(raw) as Map<String,dynamic>;final b=(d['books'] as List<dynamic>? ?? []);if(!mounted)return;setState(()=>books=b);}catch(e){if(mounted)setState(()=>error='تعذر فتح ملف الكتاب المقدس: $e');}finally{if(mounted)setState(()=>loading=false);}}
  List<Map<String, dynamic>> _searchAll(String term) {
    final needle = term.trim().toLowerCase();
    final hits = <Map<String, dynamic>>[];
    if (needle.isEmpty) return hits;
    for (var bi = 0; bi < books.length; bi++) {
      final b = books[bi] as Map<String, dynamic>;
      final bookName = (b['arabicName'] ?? b['book'] ?? 'سفر').toString();
      final chapters = (b['chapters'] as List<dynamic>? ?? []);
      for (var ci = 0; ci < chapters.length; ci++) {
        final ch = chapters[ci] as Map<String, dynamic>;
        final verses = (ch['verses'] as List<dynamic>? ?? []);
        for (final item in verses) {
          final v = item as Map<String, dynamic>;
          final verseText = (v['text'] ?? '').toString();
          if (verseText.toLowerCase().contains(needle) ||
              bookName.toLowerCase().contains(needle)) {
            hits.add({
              'bookIndex': bi,
              'chapterIndex': ci,
              'bookName': bookName,
              'verseNumber': v['number'] ?? '',
              'text': verseText,
            });
            if (hits.length >= 300) return hits;
          }
        }
      }
    }
    return hits;
  }

  @override Widget build(BuildContext context){
    if(loading)return const Center(child:CircularProgressIndicator());
    if(books.isEmpty)return Center(child:Padding(padding:const EdgeInsets.all(24),child:Text(error.isEmpty?'سيتم تجهيز بيانات الكتاب المقدس أثناء البناء.':error,textAlign:TextAlign.center)));
    final b=books[bookIndex] as Map<String,dynamic>;
    final chapters=(b['chapters'] as List<dynamic>? ?? []);
    final chapter=chapters.isEmpty?null:chapters[chapterIndex] as Map<String,dynamic>;
    final verses=(chapter?['verses'] as List<dynamic>? ?? []);
    return ListView(padding:const EdgeInsets.all(16),children:[
      TextField(decoration:const InputDecoration(prefixIcon:Icon(Icons.search),labelText:'ابحث في أسماء الأسفار أو النص المعروض',border:OutlineInputBorder()),onChanged:(v)=>setState(()=>query=v)),
      const SizedBox(height:10),
      DropdownButtonFormField<int>(value:bookIndex,decoration:const InputDecoration(labelText:'السفر',border:OutlineInputBorder()),items:books.asMap().entries.map((e)=>DropdownMenuItem(value:e.key,child:Text((e.value as Map<String,dynamic>)['arabicName']?.toString()??(e.value as Map<String,dynamic>)['book']?.toString()??'سفر'))).toList(),onChanged:(v)=>setState(() { bookIndex=v??0; chapterIndex=0; })),
      const SizedBox(height:10),
      if(chapters.isNotEmpty) DropdownButtonFormField<int>(value:chapterIndex.clamp(0,chapters.length-1),decoration:const InputDecoration(labelText:'الإصحاح',border:OutlineInputBorder()),items:List.generate(chapters.length,(i)=>DropdownMenuItem(value:i,child:Text('${i+1}'))),onChanged:(v)=>setState(()=>chapterIndex=v??0)),
      const SizedBox(height:12),
      if(query.trim().isNotEmpty) ...[
        Text('نتائج البحث في الكتاب المقدس',style:const TextStyle(fontSize:18,fontWeight:FontWeight.bold,color:navy)),
        const SizedBox(height:8),
        ..._searchAll(query).map((hit)=>Card(color:Colors.white,child:ListTile(
          title:Text('${hit['bookName']} ${(hit['chapterIndex'] as int)+1}:${hit['verseNumber']}',
            style:const TextStyle(fontWeight:FontWeight.bold,color:navy)),
          subtitle:Text(hit['text'].toString(),style:const TextStyle(fontSize:16,height:1.6)),
          onTap:()=>setState((){
            bookIndex=hit['bookIndex'] as int;
            chapterIndex=hit['chapterIndex'] as int;
            query='';
          }),
        ))),
        if(_searchAll(query).isEmpty) const Padding(padding:EdgeInsets.all(18),child:Text('لا توجد نتائج مطابقة. جرّب كلمة أخرى.',textAlign:TextAlign.center)),
      ] else ...verses.map((v){final verse=v as Map<String,dynamic>;return Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(12),child:Text('${verse['number']??''}. ${verse['text']??''}',style:const TextStyle(fontSize:17,height:1.8))));}),
    ]);
  }
}

class PrayerPage extends StatefulWidget { const PrayerPage({super.key}); @override State<PrayerPage> createState()=>_PrayerPageState(); }
class _PrayerPageState extends State<PrayerPage> {
  String hour='prime'; String watch='1';
  final hours=const {'prime':'صلاة باكر','terce':'صلاة الساعة الثالثة','sext':'صلاة الساعة السادسة','none':'صلاة الساعة التاسعة','vespers':'صلاة الغروب','compline':'صلاة النوم','midnight':'صلاة نصف الليل'};
  @override Widget build(BuildContext context)=>ListView(padding:const EdgeInsets.all(16),children:[
    const Text('الأجبية',style:TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:12),
    DropdownButtonFormField<String>(value:hour,decoration:const InputDecoration(labelText:'اختر الساعة',border:OutlineInputBorder()),items:hours.entries.map((e)=>DropdownMenuItem(value:e.key,child:Text(e.value))).toList(),onChanged:(v)=>setState(()=>hour=v??'prime')),
    if(hour=='midnight') DropdownButtonFormField<String>(value:watch,decoration:const InputDecoration(labelText:'الخدمة',border:OutlineInputBorder()),items:const [DropdownMenuItem(value:'1',child:Text('الخدمة الأولى')),DropdownMenuItem(value:'2',child:Text('الخدمة الثانية')),DropdownMenuItem(value:'3',child:Text('الخدمة الثالثة'))],onChanged:(v)=>setState(()=>watch=v??'1')),
    const SizedBox(height:12),
    FilledButton.icon(onPressed:()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:hours[hour]!,path:hour=='midnight'?'/agpeya/midnight/watch/$watch':'/agpeya/$hour'))),icon:const Icon(Icons.download),label:const Text('عرض النص وحفظه تلقائيًا')),
    const SizedBox(height:10),
    const Text('النصوص التي تم تحميلها بنجاح تُحفظ على الجهاز وتُعرض عند انقطاع الإنترنت.',style:TextStyle(height:1.7,color:Colors.black54)),
  ]);
}

class ChurchPage extends StatefulWidget {
  const ChurchPage({super.key});
  @override
  State<ChurchPage> createState() => _ChurchPageState();
}

class _ChurchPageState extends State<ChurchPage> {
  bool downloading = false;
  String downloadStatus = '';

  String get today => DateTime.now().toIso8601String().substring(0, 10);

  Future<void> _downloadAvailableTexts() async {
    if (downloading) return;
    setState(() { downloading = true; downloadStatus = 'بدء حفظ النصوص المتاحة...'; });
    final requests = <MapEntry<String, String>>[
      const MapEntry('ساعات الأجبية', '/agpeya/hours'),
      const MapEntry('صلاة باكر', '/agpeya/prime'),
      const MapEntry('الساعة الثالثة', '/agpeya/terce'),
      const MapEntry('الساعة السادسة', '/agpeya/sext'),
      const MapEntry('الساعة التاسعة', '/agpeya/none'),
      const MapEntry('صلاة الغروب', '/agpeya/vespers'),
      const MapEntry('صلاة النوم', '/agpeya/compline'),
      const MapEntry('نصف الليل — الخدمة الأولى', '/agpeya/midnight/watch/1'),
      const MapEntry('نصف الليل — الخدمة الثانية', '/agpeya/midnight/watch/2'),
      const MapEntry('نصف الليل — الخدمة الثالثة', '/agpeya/midnight/watch/3'),
      MapEntry('قراءات القطمارس لليوم', '/readings/$today?detailed=true'),
      MapEntry('سنكسار اليوم', '/synaxarium/$today'),
      MapEntry('الموسم الطقسي', '/season/$today'),
      MapEntry('الصوم', '/fasting/$today'),
      const MapEntry('تسبحة الأحد السنوية', '/tasbeha/sunday?lang=ar'),
      const MapEntry('تسبحة الاثنين السنوية', '/tasbeha/monday?lang=ar'),
      const MapEntry('تسبحة الثلاثاء السنوية', '/tasbeha/tuesday?lang=ar'),
      const MapEntry('تسبحة الأربعاء السنوية', '/tasbeha/wednesday?lang=ar'),
      const MapEntry('تسبحة الخميس السنوية', '/tasbeha/thursday?lang=ar'),
      const MapEntry('تسبحة الجمعة السنوية', '/tasbeha/friday?lang=ar'),
      const MapEntry('تسبحة السبت السنوية', '/tasbeha/saturday?lang=ar'),
    ];
    var saved = 0;
    final failed = <String>[];
    for (final item in requests) {
      try {
        final uri = Uri.parse('$apiRoot${item.value}');
        await KenozApi.get(uri.path.substring(Uri.parse(apiRoot).path.length),
            query: uri.queryParameters.isEmpty ? null : uri.queryParameters);
        saved++;
      } catch (_) {
        failed.add(item.key);
      }
      if (mounted) setState(() => downloadStatus = 'تم حفظ $saved من ${requests.length} عناصر...');
    }
    if (mounted) {
      setState(() {
        downloading = false;
        downloadStatus = failed.isEmpty
            ? 'اكتمل حفظ $saved عنصرًا. يمكن فتح العناصر التي تم تحميلها دون إنترنت.'
            : 'حُفظ $saved عنصرًا، وتعذر تحميل ${failed.length}. يلزم الإنترنت لإعادة المحاولة.';
      });
      if (failed.isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تعذر تحميل: ${failed.take(4).join('، ')}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      const Text('مكتبة النصوص الكنسية', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: navy)),
      const SizedBox(height: 6),
      const Text('الأجبية والخولاجي والقطمارس والسنكسار', style: TextStyle(color: Colors.black54)),
      const SizedBox(height: 12),
      _item(context, 'الأجبية — صلوات السواعي', Icons.auto_stories, '/agpeya/hours'),
      Card(
        color: Colors.white,
        child: ListTile(
          leading: const Icon(Icons.library_books, color: gold),
          title: const Text('استيراد مكتبة النصوص المحلية'),
          subtitle: const Text('الخولاجي والقطمارس والسنكسار والتسبحة والخدمات — تعمل بعد الاستيراد دون إنترنت'),
          trailing: const Icon(Icons.chevron_left),
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const LocalLibraryPage())),
        ),
      ),
      _item(context, 'قطمارس اليوم — القراءات', Icons.menu_book, '/readings/$today?detailed=true'),
      _item(context, 'سنكسار اليوم', Icons.event_note, '/synaxarium/$today'),
      const Divider(height: 28),
      const Text('تنزيل للاستخدام دون إنترنت', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: navy)),
      const SizedBox(height: 8),
      FilledButton.icon(
        onPressed: downloading ? null : _downloadAvailableTexts,
        icon: downloading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.download_for_offline),
        label: Text(downloading ? 'جارٍ الحفظ...' : 'تحميل الأجبية والقراءات والنصوص المتاحة'),
      ),
      if (downloadStatus.isNotEmpty) ...[
        const SizedBox(height: 8),
        Text(downloadStatus, style: const TextStyle(height: 1.5, color: Colors.black54)),
      ],
      const SizedBox(height: 20),
      const Text('خدمات طقسية إضافية', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: navy)),
      const SizedBox(height: 8),
      _item(context, 'التسبحة السنوية', Icons.music_note, '/tasbeha/sunday?lang=ar'),
      _item(context, 'الموسم الطقسي', Icons.calendar_month, '/season/$today'),
      _item(context, 'الصوم', Icons.restaurant, '/fasting/$today'),
      const SizedBox(height: 10),
      const Text('الحفظ دون إنترنت يشمل العناصر التي تم تنزيلها بنجاح فقط. الخولاجي الكامل ما زال يحتاج إلى دمج الملفات المحلية المستخرجة.', style: TextStyle(height: 1.6, color: Colors.black54)),
    ],
  );

  Widget _item(BuildContext c, String s, IconData i, String p) => Card(
    color: Colors.white,
    child: ListTile(
      leading: Icon(i, color: gold),
      title: Text(s),
      trailing: const Icon(Icons.chevron_left),
      onTap: () => Navigator.push(c, MaterialPageRoute(builder: (_) => DetailPage(title: s, path: p))),
    ),
  );
}


class LocalLibraryPage extends StatefulWidget {
  const LocalLibraryPage({super.key});
  @override State<LocalLibraryPage> createState() => _LocalLibraryPageState();
}
class _LocalLibraryPageState extends State<LocalLibraryPage> {
  bool busy = true;
  String status = '';
  List<String> files = [];
  late Directory localDir;

  @override void initState() { super.initState(); _init(); }
  Future<void> _init() async {
    final base = await getApplicationDocumentsDirectory();
    localDir = Directory('${base.path}/kenoz_local_content');
    if (!await localDir.exists()) await localDir.create(recursive: true);
    await _refresh();
    if (mounted) setState(() => busy = false);
  }
  Future<void> _refresh() async {
    if (!await localDir.exists()) return;
    final names = localDir.listSync().whereType<File>()
      .map((f) => f.uri.pathSegments.last)
      .where((n) => n.endsWith('.json') && n != 'manifest.json').toList()..sort();
    if (mounted) setState(() => files = names);
  }
  Future<void> _importZip() async {
    if (busy) return;
    try {
      setState(() { busy = true; status = 'اختر ملف حزمة محتوى كنوز ZIP...'; });
      final picked = await FilePicker.platform.pickFiles(type: FileType.custom,
        allowedExtensions: ['zip'], withData: true);
      if (picked == null || picked.files.isEmpty) {
        if (mounted) setState(() { busy = false; status = 'تم إلغاء الاختيار.'; });
        return;
      }
      final bytes = picked.files.single.bytes;
      if (bytes == null) throw Exception('تعذر قراءة الملف المختار.');
      final archive = ZipDecoder().decodeBytes(bytes);
      var count = 0;
      for (final entry in archive) {
        if (!entry.isFile || !entry.name.toLowerCase().endsWith('.json')) continue;
        final name = entry.name.split('/').last;
        if (name.contains('..') || name.contains('/') || name.contains(r'\\')) continue;
        final content = entry.content;
        final out = File('${localDir.path}/$name');
        await out.writeAsBytes(content is List<int> ? content : List<int>.from(content), flush: true);
        count++;
      }
      await _refresh();
      if (mounted) setState(() { busy = false; status = 'تم استيراد $count ملفًا. المحتوى محفوظ على الجهاز ويمكن فتحه دون إنترنت.'; });
    } catch (e) {
      if (mounted) setState(() { busy = false; status = 'فشل الاستيراد: $e'; });
    }
  }
  String _title(Map<String, dynamic> item) {
    final text = (item['text'] ?? '').toString().trim();
    if (text.isNotEmpty) return text.split('\n').first;
    final rows = item['rows'];
    if (rows is List) {
      for (final row in rows) {
        if (row is List) {
          for (final cell in row) {
            final value = cell.toString().trim();
            if (value.isNotEmpty && !RegExp(r'^[0-9]+(?:\.0)?$').hasMatch(value)) return value;
          }
        }
      }
    }
    return (item['path'] ?? 'نص كنسي').toString().split('/').last;
  }
  Future<void> _openCategory(String name) async {
    try {
      final decoded = jsonDecode(await File('${localDir.path}/$name').readAsString()) as Map<String, dynamic>;
      final items = (decoded['items'] as List<dynamic>? ?? []);
      if (!mounted) return;
      Navigator.push(context, MaterialPageRoute(builder: (_) => LocalCategoryPage(
        title: _categoryLabel(name), items: items.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
        titleFor: _title)));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('تعذر فتح الملف: $e')));
    }
  }
  String _categoryLabel(String name) {
    const labels = {'kholagy.json':'الخولاجي','katamars.json':'القطمارس','synaxarium.json':'السنكسار',
      'dallal.json':'الدلال','psalmody_annual.json':'التسبحة السنوية','absalmody.json':'الإبصلمودية',
      'prostrations.json':'صلوات السجود','shawahed.json':'الشواهد'};
    return labels[name] ?? name.replaceAll('.json','');
  }
  @override Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
    const Text('مكتبة النصوص المحلية', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: navy)),
    const SizedBox(height: 8),
    const Text('استورد ملف ZIP مرة واحدة؛ تُحفظ ملفات النصوص داخل التطبيق وتظل متاحة دون اتصال.', style: TextStyle(height: 1.5)),
    const SizedBox(height: 12),
    FilledButton.icon(onPressed: busy ? null : _importZip,
      icon: busy ? const SizedBox(width:18,height:18,child:CircularProgressIndicator(strokeWidth:2,color:Colors.white)) : const Icon(Icons.folder_open),
      label: Text(busy ? 'جارٍ الاستيراد...' : 'اختيار حزمة المحتوى ZIP')),
    if (status.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 10), child: Text(status, style: const TextStyle(height:1.5))),
    const Divider(),
    if (files.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('لم يتم استيراد ملفات بعد. نزّل حزمة محتوى كنوز ثم اخترها من هنا.', textAlign: TextAlign.center))
    else ...files.map((name) => Card(color: Colors.white, child: ListTile(
      leading: const Icon(Icons.menu_book, color: gold), title: Text(_categoryLabel(name)),
      subtitle: Text(name), trailing: const Icon(Icons.chevron_left), onTap: () => _openCategory(name))))
  ]);
}

class LocalCategoryPage extends StatelessWidget {
  final String title;
  final List<Map<String, dynamic>> items;
  final String Function(Map<String, dynamic>) titleFor;
  const LocalCategoryPage({super.key, required this.title, required this.items, required this.titleFor});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: items.isEmpty
          ? const Center(child: Text('لا توجد نصوص في هذا القسم.'))
          : ListView.builder(
              itemCount: items.length,
              itemBuilder: (context, index) {
                final item = items[index];
                final label = titleFor(item);
                return Card(
                  color: Colors.white,
                  margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  child: ListTile(
                    title: Text(label, maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Text(
                      (item['path'] ?? '').toString().split('/').skip(2).join('/'),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => LocalTextPage(title: label, item: item),
                        ),
                      );
                    },
                  ),
                );
              },
            ),
    );
  }
}

class LocalTextPage extends StatelessWidget {
  final String title;
  final Map<String, dynamic> item;
  const LocalTextPage({super.key, required this.title, required this.item});
  @override Widget build(BuildContext context) {
    final buffer = StringBuffer();
    final text = (item['text'] ?? '').toString().trim();
    if (text.isNotEmpty) buffer.writeln(text);
    final rows = item['rows'];
    if (rows is List) {
      for (final row in rows) {
        if (row is! List) continue;
        final cells = row.map((e) => e.toString().trim()).where((e) => e.isNotEmpty).toList();
        if (cells.isNotEmpty) {
          buffer.writeln();
          buffer.writeln(cells.join('\n'));
        }
      }
    }
    final body = buffer.toString().trim();
    return Scaffold(appBar: AppBar(title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis)),
      body: body.isEmpty ? const Center(child: Text('هذا الملف لا يحتوي على نص قابل للعرض.')) :
        SelectionArea(child: ListView(padding: const EdgeInsets.all(18), children: [
          Text(title, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.bold, color: navy)),
          const SizedBox(height: 14),
          Text(body, textDirection: TextDirection.rtl, style: const TextStyle(fontSize: 17, height: 1.9)),
          const SizedBox(height: 20),
          Text('المصدر: ${item['path'] ?? 'ملف محلي'}', style: const TextStyle(fontSize: 11, color: Colors.black45)),
        ])));
  }
}

class NotesPage extends StatefulWidget { const NotesPage({super.key}); @override State<NotesPage> createState()=>_NotesPageState(); }
class _NotesPageState extends State<NotesPage> {
  final controller=TextEditingController(); List<String> notes=[];
  @override void initState(){super.initState();_load();}
  Future<void> _load()async{final p=await SharedPreferences.getInstance();if(mounted)setState(()=>notes=p.getStringList('kenoz_notes')??[]);}
  Future<void> _add()async{final s=controller.text.trim();if(s.isEmpty)return;final p=await SharedPreferences.getInstance();notes=[...notes,s];await p.setStringList('kenoz_notes',notes);controller.clear();if(mounted)setState((){});}
  @override void dispose(){controller.dispose();super.dispose();}
  @override Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.all(16),child:Column(children:[
    const Text('ملاحظاتي الروحية',style:TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:12),TextField(controller:controller,maxLines:3,decoration:const InputDecoration(labelText:'اكتب ملاحظة أو تأملًا',border:OutlineInputBorder())),
    const SizedBox(height:8),Align(alignment:Alignment.centerLeft,child:FilledButton(onPressed:_add,child:const Text('حفظ'))),
    const Divider(),Expanded(child:notes.isEmpty?const Center(child:Text('لا توجد ملاحظات بعد.')):ListView.builder(itemCount:notes.length,itemBuilder:(c,i)=>Card(color:Colors.white,child:ListTile(title:Text(notes[i]),trailing:IconButton(icon:const Icon(Icons.delete_outline),onPressed:()async{notes.removeAt(i);final p=await SharedPreferences.getInstance();await p.setStringList('kenoz_notes',notes);if(mounted)setState((){});}))))),
  ]));
}

class DetailPage extends StatefulWidget { final String title,path; const DetailPage({super.key,required this.title,required this.path}); @override State<DetailPage> createState()=>_DetailPageState(); }
class _DetailPageState extends State<DetailPage> {
  dynamic data; bool loading=true,offline=false; String error='';
  @override void initState(){super.initState();_load();}
  Future<void> _load()async{
    setState(()=>loading=true);
    try{
      final baseUri = Uri.parse(apiRoot);
      final uri = Uri.parse(widget.path.startsWith('http')
          ? widget.path
          : '$apiRoot${widget.path.startsWith('/') ? widget.path : '/${widget.path}'}');
      final apiPath = uri.path.startsWith(baseUri.path)
          ? uri.path.substring(baseUri.path.length)
          : uri.path;
      final result = await KenozApi.get(
        apiPath.isEmpty ? '/' : apiPath,
        query: uri.queryParameters.isEmpty ? null : uri.queryParameters,
      );
      if(mounted)setState(() { data=result.data; offline=result.offline; });
    }catch(e){if(mounted)setState(()=>error='لم نتمكن من جلب هذا المحتوى ولا توجد نسخة محفوظة بعد. اتصل بالإنترنت وحاول مرة أخرى.');}
    finally{if(mounted)setState(()=>loading=false);}
  }
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:Text(widget.title)),body:loading?const Center(child:CircularProgressIndicator()):error.isNotEmpty?Center(child:Padding(padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[const Icon(Icons.cloud_off,size:42,color:gold),const SizedBox(height:12),Text(error,textAlign:TextAlign.center),const SizedBox(height:12),FilledButton(onPressed:_load,child:const Text('إعادة المحاولة'))]))):Column(children:[
    Container(width:double.infinity,padding:const EdgeInsets.all(10),color:offline?const Color(0xFFFFF0D5):const Color(0xFFE3F4E8),child:Text(offline?'معروض من النسخة المحفوظة دون إنترنت':'تم التحميل — حُفظ تلقائيًا على الجهاز',textAlign:TextAlign.center)),
    Expanded(child:ListView(padding:const EdgeInsets.all(16),children:[_render(data)])),
  ]));
  Widget _render(dynamic v){
    if(v==null)return const SizedBox.shrink();
    if(v is Map){return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:v.entries.map((e)=>Padding(padding:const EdgeInsets.only(bottom:8),child:Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(12),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(_label(e.key.toString()),style:const TextStyle(fontWeight:FontWeight.bold,color:navy,fontSize:16)),const SizedBox(height:6),_render(e.value)]))))).toList());}
    if(v is List)return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:v.map((x)=>Padding(padding:const EdgeInsets.only(bottom:6),child:_render(x))).toList());
    return SelectableText(v.toString(),style:const TextStyle(fontSize:16,height:1.7));
  }
  String _label(String s){const m={'vespers':'عشية','matins':'باكر','liturgy':'القداس','pauline':'البولس','catholic':'الكاثوليكون','praxis':'الإبركسيس','psalm':'المزمور','gospel':'الإنجيل','synaxarium':'السنكسار','readings':'القراءات','date':'التاريخ','title':'العنوان','text':'النص','content':'المحتوى','description':'التفاصيل','name':'الاسم','reference':'المرجع','season':'الموسم الطقسي','fasting':'الصوم','saints':'القديسون'};return m[s]??s.replaceAll('_',' ');}
}
