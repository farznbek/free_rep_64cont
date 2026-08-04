<?php
/* =====================================================================
   KINO BOT — bitta fayldan iborat, webhook orqali ishlaydigan bot
   Til: PHP 8+  |  Baza: SQLite (qo'shimcha sozlashsiz ishlaydi)
   =====================================================================
   O'RNATISH TARTIBI (oddiy odam uchun):
   1) Shu faylni "index.php" nomi bilan hostingingizga (public_html ichiga) yuklang.
   2) Pastdagi "SOZLAMALAR" bo'limini to'ldiring (token, ID va h.k.).
   3) Botni @BotFather orqali kanallarga ADMIN qilib qo'shing:
        - kinolar bazasi kanali (STORAGE_CHANNEL_ID)
        - kino kodlari kanali (CODES_CHANNEL_ID)
        - majburiy obuna kanallari (bular admin panel ichidan qo'shiladi)
   4) Brauzerda quyidagi manzilni oching (TOKEN o'rniga o'zingiznikini yozing,
      SITE_URL o'rniga shu faylning to'liq manzilini yozing, masalan
      https://sizningsayt.uz/index.php):
        https://api.telegram.org/bot<TOKEN>/setWebhook?url=<SITE_URL>
      Muvaffaqiyatli bo'lsa "ok":true degan javob qaytadi.
   5) Hostingda "Cron Job" (rejalashtirilgan vazifa) qo'shing — har 5-10
      daqiqada quyidagi manzilga kirib turishi kerak (bu 24soatlik kino
      o'chirish va VIP muddati tugashini kuzatib turadi):
        https://sizningsayt.uz/index.php?cron=SIZNING_CRON_MAXFIY_KALITINGIZ
   ===================================================================== */


/* ===================== 1) SOZLAMALAR (SHU YERNI TO'LDIRING) ===================== */

define('BOT_TOKEN', '8917513576:AAHiiGf7BwBzr2l9JF1Rs9X8Crz2ZVO2La4');      // masalan: 123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
define('BOT_USERNAME', 'flurnexbot');                                    // @ belgisisiz, masalan: kino_bot

define('SUPER_ADMIN_ID', 6467718270);                                    // sizning shaxsiy Telegram ID raqamingiz (@userinfobot orqali oling) — 123456789 o'rniga o'zingiznikini yozing!

define('STORAGE_CHANNEL_ID', '-1004323688997');                          // kino fayllari saqlanadigan YOPIQ kanal (bot admin bo'lishi shart)
define('CODES_CHANNEL_ID', '@flurnex');                                  // kino kodlari e'lon qilinadigan kanal (bot admin bo'lishi shart)

define('CRON_SECRET_KEY', 'Farzn200907');                                // cron manzili uchun maxfiy kalit (taxmin qilib bo'lmaydigan so'z yozing)

define('DEFAULT_DAILY_LIMIT', 5);                                        // oddiy foydalanuvchilar uchun boshlang'ich kunlik kino limiti

/* ------- PREMIUM (animatsiyali) EMOJI — ixtiyoriy bo'lim -------
   SHART: bu faqat SUPER_ADMIN_ID akkauntida Telegram Premium bo'lsa ishlaydi
   (bot shu odam nomidan yuboradi degani). Kanal postlarida ishlamaydi,
   faqat botning shaxsiy/guruh xabarlarida ishlaydi.

   custom_emoji_id qanday olinadi (3 usuldan biri):
   1) O'zingizda bor premium emojini istalgan chatga yozing, so'ng shu
      xabarni @RawDataBot yoki @ShowJsonBot ga forward qiling — javobda
      "custom_emoji_id" raqamini ko'rasiz.
   2) Yoki Bot API orqali getStickerSet metodini premium emoji to'plami
      nomi bilan chaqiring (masalan brauzerda):
      https://api.telegram.org/bot<TOKEN>/getStickerSet?name=<to'plam_nomi>
      — natijadagi har bir sticker'ning "custom_emoji_id" maydoni bo'ladi.
   3) Tayyor premium-emoji ID bazalaridan foydalanish (internetda mavjud).

   Pastdagi ro'yxatga "oddiy emoji" => "custom_emoji_id" tarzida
   to'ldiring. Chapdagi oddiy emoji xuddi shu ko'rinishda kod ichida
   ishlatilgan bo'lishi kerak (masalan 🎬, 💎, ✅ va h.k.).
   Ro'yxat bo'sh qolsa yoki USE_PREMIUM_EMOJI false bo'lsa, bot avvalgidek
   oddiy emojilar bilan ishlayveradi — hech narsa buzilmaydi.

   ESLATMA: quyidagi ro'yxat FAQAT boshlang'ich (standart) qiymat — botni
   ishga tushirgandan keyin buni Admin panel → "🎨 Premium emoji" bo'limi
   orqali istalgan vaqtda o'zgartirishingiz mumkin (kod faylini qayta
   tahrirlash shart emas). Bot birinchi navbatda bazadagi saqlangan
   ro'yxatni ishlatadi, agar u bo'lmasa — shu standart ro'yxatga qaytadi. */

define('USE_PREMIUM_EMOJI', true); // yoqish uchun true qiling

function defaultEmojiMap(): array {
    return [
        '✅' => '5427009714745517609',
        '❌' => '5465665476971471368',
        '💎' => '5471952986970267163',
        '🎬' => '5375464961822695044',
        '✏️' => '5334673106202010226',
        '➕' => '5226945370684140473',
        '🌟' => '5458799228719472718',
        '📨' => '5406631276042002796',
        '📊' => '5431577498364158238',
        '👥' => '5372926953978341366',
        '👤' => '5373012449597335010',
        '❗️' => '5467928559664242360',
        '✨' => '5472164874886846699',
        '🔗' => '5375129357373165375',
        '🏆' => '5409008750893734809',
        '📤' => '5433614747381538714',
        '🔥' => '5420315771991497307',
        '👇' => '5470177992950946662',
        '💰' => '5375296873982604963',
        '🖼' => '5375074927252621134',
        '🔑' => '5330115548900501467',
        '➖' => '5229113891081956317',
        '🎉' => '5436040291507247633',
        '✍️' => '5470060791883374114',
        '💬' => '5465300082628763143',
        '📝' => '5334882760735598374',
        '👍' => '5397916757333654639',
        '🔒' => '4904500559203009298',
        '📡' => '5256134032852278918',
        '✈️' => '5372849966689566579',
        '📥' => '5443127283898405358',
        // Quyidagilar yangi qo'shilgan bo'sh joylar — real custom_emoji_id
        // qiymati Admin panel → "🎨 Premium emoji" bo'limidan kiritilmaguncha
        // botning boshqa joylariga ta'sir qilmaydi (oddiy holatda ishlayveradi).
        '⬅️' => '',
        '🗑' => '',
        '🎥' => '',
        '💾' => '',
        '🌐' => '',
        '🛠' => '',
        '🔁' => '',
        '💳' => '',
        '🔢' => '',
        '📄' => '',
        '↪️' => '',
        '✉️' => '',
        '⏸' => '',
        '▶️' => '',
        '🧑‍💻' => '',
    ];
}

// Berilgan oddiy emoji uchun premium custom_emoji_id qaytaradi (agar
// admin panel/standart ro'yxatda mavjud va bo'sh bo'lmasa), aks holda null —
// null qaytsa btn()/ubtn() oddiy (rangsiz/ikonkasiz) ishlayveradi, hech narsa
// buzilmaydi.
function emIcon(string $emoji): ?string {
    $v = emojiMap()[$emoji] ?? null;
    return $v ? $v : null;
}

// Joriy premium emoji ro'yxatini bazadan o'qiydi (admin panel orqali
// o'zgartirilgan bo'lsa shuni ishlatadi), aks holda standart ro'yxatga qaytadi.
function emojiMap(): array {
    $raw = getSetting('emoji_map_json', '');
    if ($raw) {
        $decoded = json_decode($raw, true);
        if (is_array($decoded) && !empty($decoded)) return $decoded;
    }
    return defaultEmojiMap();
}

/* =================== SOZLAMALAR SHU YERDA TUGADI =================== */


/* ===================== 2) TIZIM SOZLAMALARI (tegmang) ===================== */

error_reporting(E_ALL & ~E_DEPRECATED & ~E_NOTICE);
date_default_timezone_set('Asia/Tashkent');
set_time_limit(0);
ignore_user_abort(true);

define('DB_FILE', __DIR__ . '/bot.db');
define('API_URL', 'https://api.telegram.org/bot' . BOT_TOKEN . '/');
define('BOT_ID', (int) explode(':', BOT_TOKEN)[0]);

// str_starts_with() faqat PHP 8.0+ da mavjud. Hostingingizda eski PHP versiyasi
// bo'lsa ham bot ishlashi uchun shu funksiyani o'zimiz qo'shib qo'yamiz.
if (!function_exists('str_starts_with')) {
    function str_starts_with(string $haystack, string $needle): bool {
        return $needle === '' || strncmp($haystack, $needle, strlen($needle)) === 0;
    }
}

/* ------------------------- Baza ulanishi va jadvallar ------------------------- */

function db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $pdo = new PDO('sqlite:' . DB_FILE);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec('PRAGMA journal_mode = WAL;');
    }
    return $pdo;
}

function initDb(): void {
    $sql = "
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_vip INTEGER DEFAULT 0,
        vip_until INTEGER DEFAULT 0,
        vip_plan_id INTEGER,
        daily_limit_override INTEGER,
        joined_at INTEGER,
        is_blocked INTEGER DEFAULT 0,
        last_active_at INTEGER,
        state TEXT,
        state_data TEXT
    );
    CREATE TABLE IF NOT EXISTS admins (
        telegram_id INTEGER PRIMARY KEY,
        role TEXT,
        added_by INTEGER,
        added_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        title TEXT,
        type TEXT DEFAULT 'public',
        invite_link TEXT,
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        title TEXT,
        description TEXT,
        storage_message_id INTEGER,
        added_by INTEGER,
        created_at INTEGER,
        views_count INTEGER DEFAULT 0,
        access TEXT DEFAULT 'all'
    );
    CREATE TABLE IF NOT EXISTS movie_deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER,
        user_id INTEGER,
        chat_id INTEGER,
        message_id INTEGER,
        delete_at INTEGER,
        deleted INTEGER DEFAULT 0,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS daily_views (
        user_id INTEGER,
        day TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, day)
    );
    CREATE TABLE IF NOT EXISTS vip_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        duration_days INTEGER,
        description TEXT,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS vip_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_id INTEGER,
        full_name TEXT,
        receipt_file_id TEXT,
        receipt_type TEXT,
        status TEXT DEFAULT 'pending',
        admin_id INTEGER,
        created_at INTEGER,
        resolved_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS settings (
        skey TEXT PRIMARY KEY,
        svalue TEXT
    );
    CREATE TABLE IF NOT EXISTS user_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event TEXT,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS channel_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_db_id INTEGER,
        user_id INTEGER,
        action TEXT,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS saved_movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id INTEGER,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_type TEXT,
        text TEXT,
        file_id TEXT,
        button_text TEXT,
        button_url TEXT,
        duration_seconds INTEGER DEFAULT 10,
        target_codes TEXT DEFAULT 'all',
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        admin_id INTEGER,
        admin_message_id INTEGER,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER,
        ep_number INTEGER,
        storage_message_id INTEGER,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS promo_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        title TEXT,
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS channel_ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_channel_id INTEGER,
        ad_mode TEXT DEFAULT 'top_post',
        content_mode TEXT DEFAULT 'normal',
        content_type TEXT,
        text TEXT,
        file_id TEXT,
        button_text TEXT,
        button_url TEXT,
        forward_chat_id TEXT,
        forward_message_id INTEGER,
        delay_minutes INTEGER DEFAULT 30,
        requeue_minutes INTEGER DEFAULT 60,
        auto_delete_prev INTEGER DEFAULT 1,
        times_json TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS channel_ad_state (
        channel_ad_id INTEGER PRIMARY KEY,
        last_ad_message_id INTEGER,
        last_ad_sent_at INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS promo_channel_state (
        promo_channel_id INTEGER PRIMARY KEY,
        last_regular_post_at INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS channel_ad_sent_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_ad_id INTEGER,
        slot_date TEXT,
        slot_time TEXT
    );
    ";
    db()->exec($sql);

    // Eski bazalarda yo'q ustunlarni qo'shib qo'yamiz (xato chiqsa e'tibor bermaymiz — demak allaqachon bor)
    $migrations = [
        "ALTER TABLE channels ADD COLUMN invite_link TEXT",
        "ALTER TABLE channels ADD COLUMN description TEXT",
        "ALTER TABLE movies ADD COLUMN access TEXT DEFAULT 'all'",
        "ALTER TABLE daily_views ADD COLUMN bonus INTEGER DEFAULT 0",
        "ALTER TABLE vip_payments ADD COLUMN exact_amount INTEGER",
        "ALTER TABLE vip_payments ADD COLUMN reserved_until INTEGER",
        "ALTER TABLE vip_payments ADD COLUMN method TEXT",
        "ALTER TABLE users ADD COLUMN kb_shown INTEGER DEFAULT 0",
        "ALTER TABLE ads ADD COLUMN purpose TEXT DEFAULT 'movie'",
        "ALTER TABLE movies ADD COLUMN type TEXT DEFAULT 'movie'",
        "ALTER TABLE ads ADD COLUMN mode TEXT DEFAULT 'normal'",
        "ALTER TABLE ads ADD COLUMN forward_chat_id TEXT",
        "ALTER TABLE ads ADD COLUMN forward_message_id INTEGER",
    ];
    foreach ($migrations as $m) {
        try { db()->exec($m); } catch (Throwable $e) { /* ustun allaqachon mavjud */ }
    }
}
initDb();

// Bir martalik migratsiya: eski "kb_shown" belgisini tozalaymiz, shunda
// TOP10/Saqlanganlarim tugmalari endi to'g'ri (faqat VIP'ga) qayta
// ko'rsatiladi — avvalgi (hammaga chiqaverdigan) noto'g'ri klaviatura
// o'rniga.
if (getSetting('kb_migration_v2', '') !== 'done') {
    db()->exec('UPDATE users SET kb_shown = 0');
    setSetting('kb_migration_v2', 'done');
}

// Bir martalik migratsiya (v3): "kb_shown" ilgari noto'g'ri (masalan xatolik
// bilan) belgilanib qolgan bo'lishi mumkin edi — shuning uchun Status/Adminga
// murojaat tugmalari ba'zi foydalanuvchilarga umuman ko'rinmay qolgandi. Buni
// bir marta qayta tozalab, hammaga qaytadan to'g'ri ko'rsatamiz.
if (getSetting('kb_migration_v3', '') !== 'done') {
    db()->exec('UPDATE users SET kb_shown = 0');
    setSetting('kb_migration_v3', 'done');
}

/* ===================== 3) YORDAMCHI FUNKSIYALAR ===================== */

function tgApi(string $method, array $params = []) {
    $ch = curl_init(API_URL . $method);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $params);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 20);
    $res = curl_exec($ch);
    curl_close($ch);
    return $res ? json_decode($res, true) : null;
}

function sendMessage($chatId, string $text, array $kb = null) {
    $p = array_merge(['chat_id' => $chatId, 'disable_web_page_preview' => true], textPayload($text));
    if ($kb !== null) $p['reply_markup'] = json_encode($kb);
    return tgApi('sendMessage', $p);
}

function editMessageText($chatId, $messageId, string $text, array $kb = null) {
    $p = array_merge(['chat_id' => $chatId, 'message_id' => $messageId, 'disable_web_page_preview' => true], textPayload($text));
    if ($kb !== null) $p['reply_markup'] = json_encode($kb);
    return tgApi('editMessageText', $p);
}

function answerCb($cbId, string $text = '', bool $alert = false) {
    tgApi('answerCallbackQuery', ['callback_query_id' => $cbId, 'text' => $text, 'show_alert' => $alert]);
}

function h($s): string { return htmlspecialchars((string) $s, ENT_QUOTES); }

function ikb(array $rows): array { return ['inline_keyboard' => $rows]; }
// Bot API 9.4 (2026-02-09) dan beri tugmalarga rang (style) va premium emoji
// ikonka (icon_custom_emoji_id) qo'shish mumkin.
// Tugma matni boshidagi bitta oddiy emojini olib tashlaydi — bu premium
// ikonka (icon_custom_emoji_id) qo'yilganda ikkita emoji birga
// ko'rinib qolmasligi uchun kerak (faqat premium ikonka qolishi kerak).
function stripLeadingEmoji(string $text): string {
    $pattern = '/^(?:[\x{1F000}-\x{1FFFF}]|[\x{2190}-\x{21FF}]|[\x{2300}-\x{27BF}]|[\x{2B00}-\x{2BFF}])\x{FE0F}?\s*/u';
    return preg_replace($pattern, '', $text);
}

// $style: 'primary' (ko'k), 'success' (yashil), 'danger' (qizil), yoki null (standart)
// $icon: emojiMap() dagi custom_emoji_id qiymati (faqat SUPER_ADMIN_ID Premium bo'lsa ishlaydi)
function btn(string $text, string $cb, ?string $style = null, ?string $icon = null): array {
    if ($icon && USE_PREMIUM_EMOJI) { $b = ['text' => stripLeadingEmoji($text), 'callback_data' => $cb, 'icon_custom_emoji_id' => $icon]; }
    else { $b = ['text' => $text, 'callback_data' => $cb]; }
    if ($style) $b['style'] = $style;
    return $b;
}
function ubtn(string $text, string $url, ?string $style = null, ?string $icon = null): array {
    if ($icon && USE_PREMIUM_EMOJI) { $b = ['text' => stripLeadingEmoji($text), 'url' => $url, 'icon_custom_emoji_id' => $icon]; }
    else { $b = ['text' => $text, 'url' => $url]; }
    if ($style) $b['style'] = $style;
    return $b;
}
// VIP/premium mavzudagi tugmalar uchun qulay ikonka ID (emojiMap() dagi 💎 dan)
function vipIcon(): ?string { return emojiMap()['💎'] ?? null; }

/* ------------------------- Premium emoji / formatlash entities ------------------------- */
// Telegram offset/length UTF-16 kod birliklarida hisoblanadi (oddiy strlen emas)
function utf16Length(string $s): int {
    return (int) (strlen(mb_convert_encoding($s, 'UTF-16LE', 'UTF-8')) / 2);
}

function customEmojiEntities(string $plain): array {
    if (!USE_PREMIUM_EMOJI || empty(emojiMap())) return [];
    $entities = [];
    foreach (emojiMap() as $emoji => $cid) {
        if ($emoji === '' || !$cid) continue;
        $searchPos = 0;
        while (($idx = mb_strpos($plain, $emoji, $searchPos, 'UTF-8')) !== false) {
            $before = mb_substr($plain, 0, $idx, 'UTF-8');
            $entities[] = [
                'type' => 'custom_emoji',
                'offset' => utf16Length($before),
                'length' => utf16Length($emoji),
                'custom_emoji_id' => $cid,
            ];
            $searchPos = $idx + mb_strlen($emoji, 'UTF-8');
        }
    }
    return $entities;
}

// Oddiy <b> va <code> teglarini entity'ga aylantiradi (parse_mode o'rniga),
// so'ngra premium emoji entity'larini ham qo'shadi. $html ichidagi teglar
// olib tashlanib, sof matn qaytariladi.
function htmlToEntities(string $html): array {
    $entities = [];
    $plain = '';
    $parts = preg_split('/<(\/?)(b|code)>/i', $html, -1, PREG_SPLIT_DELIM_CAPTURE);
    $stack = [];
    $i = 0; $n = count($parts);
    while ($i < $n) {
        $plain .= $parts[$i];
        $i++;
        if ($i + 1 < $n) {
            $close = $parts[$i];
            $tag = strtolower($parts[$i + 1]);
            $i += 2;
            $offsetNow = utf16Length($plain);
            if ($close === '') {
                $stack[] = ['type' => $tag === 'b' ? 'bold' : 'code', 'start' => $offsetNow];
            } else {
                $entry = array_pop($stack);
                if ($entry) $entities[] = ['type' => $entry['type'], 'offset' => $entry['start'], 'length' => $offsetNow - $entry['start']];
            }
        }
    }
    foreach (customEmojiEntities($plain) as $e) $entities[] = $e;
    return [$plain, $entities];
}

// sendMessage/editMessageText uchun 'text' maydonini tayyorlaydi
// Talab bo'yicha BARCHA xabarlar barcha foydalanuvchilarga Bold (qalin) shriftda yuboriladi.
function boldWrap(string $html): string {
    return '<b>' . $html . '</b>';
}

function textPayload(string $html): array {
    $html = boldWrap($html);
    if (!USE_PREMIUM_EMOJI || empty(emojiMap())) {
        return ['text' => $html, 'parse_mode' => 'HTML'];
    }
    [$plain, $entities] = htmlToEntities($html);
    return ['text' => $plain, 'entities' => json_encode($entities)];
}

// sendPhoto/sendVideo/sendDocument/copyMessage uchun 'caption' maydonini tayyorlaydi
function captionPayload(string $html): array {
    $html = boldWrap($html);
    if (!USE_PREMIUM_EMOJI || empty(emojiMap())) {
        return ['caption' => $html, 'parse_mode' => 'HTML'];
    }
    [$plain, $entities] = htmlToEntities($html);
    return ['caption' => $plain, 'caption_entities' => json_encode($entities)];
}

/* ------------------------- Foydalanuvchi va state ------------------------- */

function getUser(int $id): ?array {
    $st = db()->prepare('SELECT * FROM users WHERE telegram_id = ?');
    $st->execute([$id]);
    $u = $st->fetch(PDO::FETCH_ASSOC);
    return $u ?: null;
}

function upsertUser(int $id, ?string $username, ?string $fullName): array {
    $u = getUser($id);
    $now = time();
    if (!$u) {
        $st = db()->prepare('INSERT INTO users (telegram_id, username, full_name, joined_at, last_active_at, is_blocked) VALUES (?,?,?,?,?,0)');
        $st->execute([$id, $username, $fullName, $now, $now]);
        logUserEvent($id, 'joined');
        $u = getUser($id);
    } else {
        $st = db()->prepare('UPDATE users SET username=?, full_name=?, last_active_at=?, is_blocked=0 WHERE telegram_id=?');
        $st->execute([$username, $fullName, $now, $id]);
        $u = getUser($id);
    }
    return $u;
}

function setState(int $id, ?string $state, array $data = []): void {
    $st = db()->prepare('UPDATE users SET state=?, state_data=? WHERE telegram_id=?');
    $st->execute([$state, json_encode($data), $id]);
}

function clearState(int $id): void { setState($id, null, []); }

function getStateData(array $user): array {
    $d = $user['state_data'] ?? '';
    $j = $d ? json_decode($d, true) : [];
    return is_array($j) ? $j : [];
}

function logUserEvent(int $userId, string $event): void {
    $st = db()->prepare('INSERT INTO user_events (user_id, event, created_at) VALUES (?,?,?)');
    $st->execute([$userId, $event, time()]);
}

/* ------------------------- Adminlar ------------------------- */

function getRole(int $id): ?string {
    if ($id === SUPER_ADMIN_ID) return 'super';
    $st = db()->prepare('SELECT role FROM admins WHERE telegram_id=?');
    $st->execute([$id]);
    $r = $st->fetchColumn();
    return $r ?: null;
}

function isAdmin(int $id): bool { return getRole($id) !== null; }
function isSuper(int $id): bool { return $id === SUPER_ADMIN_ID; }

/* ------------------------- Sozlamalar (settings) ------------------------- */

function getSetting(string $key, $default = null) {
    $st = db()->prepare('SELECT svalue FROM settings WHERE skey=?');
    $st->execute([$key]);
    $v = $st->fetchColumn();
    return $v === false ? $default : $v;
}
function setSetting(string $key, $value): void {
    $st = db()->prepare('INSERT INTO settings (skey, svalue) VALUES (?,?) ON CONFLICT(skey) DO UPDATE SET svalue=excluded.svalue');
    $st->execute([$key, $value]);
}
// Kinolar bazasi va kino kodlari kanallarini admin panel orqali (bazadagi
// sozlamalar orqali) tahrirlash mumkin — agar tahrirlanmagan bo'lsa, fayl
// boshidagi standart konstantalar ishlatiladi.
function storageChannelId(): string {
    $v = getSetting('storage_channel_id', '');
    return $v !== '' ? $v : STORAGE_CHANNEL_ID;
}
function codesChannelId(): string {
    $v = getSetting('codes_channel_id', '');
    return $v !== '' ? $v : CODES_CHANNEL_ID;
}

function dailyLimitFor(array $user): int {
    if (!empty($user['daily_limit_override'])) return (int) $user['daily_limit_override'];
    return (int) getSetting('daily_limit', DEFAULT_DAILY_LIMIT);
}
function isVipActive(array $user): bool {
    return (int) $user['is_vip'] === 1 && (int) $user['vip_until'] > time();
}

/* ===================== 4) MAJBURIY OBUNA (4 xil kanal turi) =====================
   Turlar:
   - public         : ommaviy kanal, @username orqali, oddiy obuna tekshiriladi
   - private_sub     : maxfiy (yopiq) kanal, taklif link orqali qo'shiladi, obuna
                        getChatMember orqali tekshiriladi (bot admin bo'lishi shart)
   - private_request : maxfiy (yopiq) kanal, "qo'shilish so'rovi" turidagi taklif
                        link. Foydalanuvchi so'rov yuborgani chat_join_request
                        orqali avtomatik qayd etiladi — qo'shimcha tekshiruv kerak
                        emas, ID so'ralmaydi.
   - optional        : majburiy EMAS, faqat qo'shimcha tugma sifatida ko'rsatiladi
                        (masalan reklama/kanal havolasi) */

function activeChannels(): array {
    $st = db()->query('SELECT * FROM channels WHERE is_active=1 ORDER BY id');
    return $st->fetchAll(PDO::FETCH_ASSOC);
}

function mandatoryChannels(): array {
    $out = [];
    foreach (activeChannels() as $c) { if ($c['type'] !== 'optional') $out[] = $c; }
    return $out;
}

function optionalChannels(): array {
    $out = [];
    foreach (activeChannels() as $c) { if ($c['type'] === 'optional') $out[] = $c; }
    return $out;
}

function isSubscribed(string $channelId, int $userId): bool {
    $r = tgApi('getChatMember', ['chat_id' => $channelId, 'user_id' => $userId]);
    if (!$r || empty($r['ok'])) return false;
    $status = $r['result']['status'] ?? '';
    return in_array($status, ['member', 'administrator', 'creator'], true);
}

function hasJoinRequest(int $channelDbId, int $userId): bool {
    $st = db()->prepare("SELECT 1 FROM channel_events WHERE channel_db_id=? AND user_id=? AND action='join_request' LIMIT 1");
    $st->execute([$channelDbId, $userId]);
    return (bool) $st->fetchColumn();
}

function channelSatisfied(array $ch, int $userId): bool {
    if ($ch['type'] === 'private_request') {
        return hasJoinRequest((int) $ch['id'], $userId);
    }
    // public va private_sub — ikkalasi ham getChatMember orqali tekshiriladi
    $ok = isSubscribed($ch['channel_id'], $userId);
    if ($ok) logChannelEvent((int) $ch['id'], $userId, 'subscribed');
    return $ok;
}

function missingChannels(int $userId): array {
    $missing = [];
    foreach (mandatoryChannels() as $ch) {
        if (!channelSatisfied($ch, $userId)) $missing[] = $ch;
    }
    return $missing;
}

function logChannelEvent(int $channelDbId, int $userId, string $action): void {
    $st = db()->prepare('SELECT 1 FROM channel_events WHERE channel_db_id=? AND user_id=? AND action=? LIMIT 1');
    $st->execute([$channelDbId, $userId, $action]);
    if (!$st->fetchColumn()) {
        $ins = db()->prepare('INSERT INTO channel_events (channel_db_id, user_id, action, created_at) VALUES (?,?,?,?)');
        $ins->execute([$channelDbId, $userId, $action, time()]);
    }
}

function channelButtonUrl(array $ch): string {
    if ($ch['type'] === 'public') return 'https://t.me/' . ltrim($ch['channel_id'], '@');
    return $ch['invite_link'] ?: 'https://t.me/';
}

function channelButtonLabel(array $ch, int $index = 0): string {
    if ($ch['type'] === 'optional') return '🔗 ' . $ch['title'];
    // Foydalanuvchiga kanal nomi ko'rsatilmaydi — faqat "🔒 Kanal N" deb chiqadi.
    // Admin panelda ("Kanallar va linklar" bo'limida) haqiqiy nomi ko'rinadi.
    return "🔒 Kanal " . $index;
}

// $missing — hali bajarilmagan MAJBURIY kanallar ro'yxati. Bunga har doim
// ixtiyoriy (optional) kanallar ham tugma sifatida qo'shib beriladi.
function sendSubscribePrompt($chatId, array $missing, string $pendingText): void {
    $rows = [];
    $i = 1;
    foreach ($missing as $ch) {
        $rows[] = [ubtn(channelButtonLabel($ch, $i), channelButtonUrl($ch), 'primary', emIcon('🔒'))];
        $i++;
    }
    foreach (optionalChannels() as $ch) {
        $rows[] = [ubtn(channelButtonLabel($ch), channelButtonUrl($ch), 'primary')];
    }
    $rows[] = [btn('✅ Tekshirish', 'chk_sub', 'success', emIcon('✅'))];
    sendMessage($chatId, $pendingText, ikb($rows));
}

/* ===================== 5) KINO YETKAZISH ===================== */

function todayKey(): string { return date('Y-m-d'); }

function getViewsToday(int $userId): int {
    $st = db()->prepare('SELECT count FROM daily_views WHERE user_id=? AND day=?');
    $st->execute([$userId, todayKey()]);
    $v = $st->fetchColumn();
    return $v === false ? 0 : (int) $v;
}
function incViewsToday(int $userId): void {
    $st = db()->prepare('INSERT INTO daily_views (user_id, day, count) VALUES (?,?,1) ON CONFLICT(user_id, day) DO UPDATE SET count = count + 1');
    $st->execute([$userId, todayKey()]);
}
function getBonusToday(int $userId): int {
    $st = db()->prepare('SELECT bonus FROM daily_views WHERE user_id=? AND day=?');
    $st->execute([$userId, todayKey()]);
    $v = $st->fetchColumn();
    return $v === false ? 0 : (int) $v;
}
function grantBonusView(int $userId): void {
    $st = db()->prepare('INSERT INTO daily_views (user_id, day, count, bonus) VALUES (?,?,0,1) ON CONFLICT(user_id, day) DO UPDATE SET bonus = bonus + 1');
    $st->execute([$userId, todayKey()]);
}

/* ===================== 5b) KINO OLDIDAN REKLAMA ===================== */

function findAdForMovie(string $code): ?array {
    $st = db()->query("SELECT * FROM ads WHERE is_active=1 AND (purpose='movie' OR purpose IS NULL) ORDER BY id");
    $ads = $st->fetchAll(PDO::FETCH_ASSOC);
    $allMatch = null;
    foreach ($ads as $ad) {
        if ($ad['target_codes'] === 'all') { if (!$allMatch) $allMatch = $ad; continue; }
        $codes = array_map('trim', explode('|', $ad['target_codes']));
        if (in_array($code, $codes, true)) return $ad;
    }
    return $allMatch;
}

// Kunlik limitni reklama orqali chetlab o'tish uchun MAXSUS reklama —
// bu kino kodlariga bog'liq emas, alohida ro'yxatdan olinadi (shu tufayli
// "chetlab o'tish" tugmasi kino uchun alohida reklama bo'lmasa ham ishlaydi).
function findLimitBypassAd(): ?array {
    $st = db()->query("SELECT * FROM ads WHERE is_active=1 AND purpose='limit_bypass' ORDER BY id DESC LIMIT 1");
    $ad = $st->fetch(PDO::FETCH_ASSOC);
    return $ad ?: null;
}

// Reklamani ko'rsatadi, oxirgi 3 soniyada 3..2..1 sanoqni ko'rsatadi, so'ng o'chiradi.
// DIQQAT: bu funksiya sleep() bilan ishlaydi — juda arzon (limitli) hostinglarda
// PHP ijro vaqti chegarasi tufayli uzoq davomiylik (masalan 60 soniyadan ortiq)
// ishlamasligi mumkin. Shu sabab reklama davomiyligini 5-20 soniya oralig'ida
// tutish tavsiya etiladi.
function showAdWithCountdown($chatId, array $ad): void {
    // 1-post: reklamaning o'zi — o'zgarmaydi, tugmasiz yoki faqat o'zining tugmasi bilan
    $msgIds = [];
    if (($ad['mode'] ?? 'normal') === 'forward' && !empty($ad['forward_chat_id']) && !empty($ad['forward_message_id'])) {
        $r = tgApi('forwardMessage', ['chat_id' => $chatId, 'from_chat_id' => $ad['forward_chat_id'], 'message_id' => $ad['forward_message_id']]);
        if ($r && !empty($r['ok'])) $msgIds[] = $r['result']['message_id'];
    } else {
        $adKb = null;
        if (!empty($ad['button_text']) && !empty($ad['button_url'])) {
            $adKb = ikb([[ubtn($ad['button_text'], $ad['button_url'], 'primary')]]);
        }
        $text = $ad['text'] ?: 'Reklama';
if (isset($text) && preg_match('/^(\/vip|vip)$/iu', trim($text))) {
    if(function_exists('openVipMenu')){openVipMenu($chat_id ?? $cid ?? $from_id);} 
}
        $p = ['chat_id' => $chatId];
        if ($adKb) $p['reply_markup'] = json_encode($adKb);
        if ($ad['content_type'] === 'photo') $r = tgApi('sendPhoto', array_merge($p, ['photo' => $ad['file_id']], captionPayload($text)));
        elseif ($ad['content_type'] === 'video') $r = tgApi('sendVideo', array_merge($p, ['video' => $ad['file_id']], captionPayload($text)));
        elseif ($ad['content_type'] === 'document') $r = tgApi('sendDocument', array_merge($p, ['document' => $ad['file_id']], captionPayload($text)));
        else $r = tgApi('sendMessage', array_merge($p, textPayload($text)));
        if ($r && !empty($r['ok'])) $msgIds[] = $r['result']['message_id'];
    }

    // 2-post: to'liq belgilangan soniyadan boshlab orqaga sanoq + VIP (chetlab o'tish) tugmasi
    // Sanoq raqami tepada, tushuntirish matni esa doim pastida turadi.
    $duration = max(1, (int) $ad['duration_seconds']);
    $skipKb = ikb([[btn('💎 VIP (reklamasiz tomosha)', 'menu_vip', 'primary', vipIcon())]]);
    $countdownText = function (int $secondsLeft) use ($duration): string {
        return "⏳ {$secondsLeft}\n\n{$duration} soniyalik reklamadan so'ng kinoni tomosha qilishingiz mumkin.\nAgar kutishni xohlamasangiz — 💎 VIP tarifga obuna bo'ling!";
    };
    $cr = tgApi('sendMessage', ['chat_id' => $chatId, 'text' => $countdownText($duration), 'reply_markup' => json_encode($skipKb)]);
    $cid = $cr['result']['message_id'] ?? null;
    for ($i = $duration - 1; $i >= 1; $i--) {
        sleep(1);
        if ($cid) editMessageText($chatId, $cid, $countdownText($i), $skipKb);
    }
    sleep(1);

    foreach ($msgIds as $mid) tgApi('deleteMessage', ['chat_id' => $chatId, 'message_id' => $mid]);
    if ($cid) tgApi('deleteMessage', ['chat_id' => $chatId, 'message_id' => $cid]);
}

function findMovieByCode(string $code): ?array {
    $st = db()->prepare('SELECT * FROM movies WHERE code=?');
    $st->execute([$code]);
    $m = $st->fetch(PDO::FETCH_ASSOC);
    return $m ?: null;
}

function findMovieById(int $id): ?array {
    $st = db()->prepare('SELECT * FROM movies WHERE id=?');
    $st->execute([$id]);
    $m = $st->fetch(PDO::FETCH_ASSOC);
    return $m ?: null;
}

// Serialning barcha qismlari (ep_number bo'yicha tartiblangan)
function movieEpisodes(int $movieId): array {
    $st = db()->prepare('SELECT * FROM episodes WHERE movie_id=? ORDER BY ep_number');
    $st->execute([$movieId]);
    return $st->fetchAll(PDO::FETCH_ASSOC);
}

// Qismlar ro'yxatini (kerak bo'lsa 2 partga bo'lib) inline tugmalar bilan yuboradi
define('EPISODE_SPLIT_THRESHOLD', 40);

function sendEpisodeList($chatId, int $movieId, ?int $part = null): void {
    $movie = findMovieById($movieId);
    if (!$movie) { sendMessage($chatId, "❌ Kino/serial topilmadi."); return; }
    $eps = movieEpisodes($movieId);
    $total = count($eps);
    if ($total === 0) { sendMessage($chatId, "❌ Bu serialga hali qismlar qo'shilmagan."); return; }

    $text = "📺 <b>" . h($movie['title']) . "</b>\n\n🎞 Tomosha qilmoqchi bo'lgan qismni tanlang:";

    if ($total > EPISODE_SPLIT_THRESHOLD && $part === null) {
        $half = (int) ceil($total / 2);
        $rows = [
            [btn("1-{$half}-qismlar", 'ep_part:' . $movieId . ':1', 'primary')],
            [btn(($half + 1) . "-{$total}-qismlar", 'ep_part:' . $movieId . ':2', 'primary')],
        ];
        sendMessage($chatId, $text, ikb($rows));
        return;
    }

    if ($total > EPISODE_SPLIT_THRESHOLD && $part !== null) {
        $half = (int) ceil($total / 2);
        $eps = $part === 1 ? array_slice($eps, 0, $half) : array_slice($eps, $half);
    }

    $rows = [];
    $line = [];
    foreach ($eps as $ep) {
        $line[] = btn((string) $ep['ep_number'], 'ep_get:' . $movieId . ':' . $ep['id'], 'primary');
        if (count($line) >= 5) { $rows[] = $line; $line = []; }
    }
    if (!empty($line)) $rows[] = $line;
    if ($total > EPISODE_SPLIT_THRESHOLD) $rows[] = [btn('⬅️ Orqaga', 'ep_parts:' . $movieId, null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

// Bitta qismni foydalanuvchiga yetkazadi — har bir qism 1 kunlik limit hisoblanadi
function deliverEpisode(int $userId, $chatId, int $movieId, int $episodeId): void {
    $movie = findMovieById($movieId);
    if (!$movie) { sendMessage($chatId, "❌ Kino/serial topilmadi."); return; }
    $st = db()->prepare('SELECT * FROM episodes WHERE id=? AND movie_id=?');
    $st->execute([$episodeId, $movieId]);
    $ep = $st->fetch(PDO::FETCH_ASSOC);
    if (!$ep) { sendMessage($chatId, "❌ Bu qism topilmadi."); return; }

    $user = getUser($userId);
    if (!$user) { $user = upsertUser($userId, null, null); }
    $vip = isVipActive($user);

    if (!$vip) {
        $limit = dailyLimitFor($user);
        $used = getViewsToday($userId);
        if ($used >= getBonusToday($userId) + $limit) {
            $limitKb = [[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]];
            if ((int) getSetting('ad_bypass_enabled', 0) === 1 && findLimitBypassAd()) {
                $limitKb[] = [btn('🎥 Reklama ko\'rib, yana 1 ta kino ko\'ring', 'watch_ad_bypass:' . $movie['code'], 'success', emIcon('🎥'))];
            }
            sendMessage($chatId, "⛔️ Siz bugungi kunlik kino olish limitingizni ({$limit} ta) ishlatib bo'ldingiz.\n\nErtaga qaytadan urinib ko'ring yoki 💎 VIP obunaga o'ting — limitsiz tomosha qiling!", ikb($limitKb));
            return;
        }
        $ad = findAdForMovie($movie['code']);
        if ($ad) showAdWithCountdown($chatId, $ad);
    }

    $captionHtml = "📺 <b>" . h($movie['title']) . "</b> — " . $ep['ep_number'] . "-qism\n\n" . h($movie['description']);
    if (!$vip) {
        $captionHtml .= "\n\n⏳ Bu kino <b>24 soatdan</b> so'ng avtomatik o'chiriladi.\nO'chirilishini xohlamasangiz — 💎 VIP obunaga o'ting!";
    }

    $params = [
        'chat_id' => $chatId,
        'from_chat_id' => storageChannelId(),
        'message_id' => $ep['storage_message_id'],
        'protect_content' => (bool) (int) getSetting('copyright_protect', 1),
    ];
    if (!$vip) $params['reply_markup'] = json_encode(ikb([[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]]));

    $res = tgApi('copyMessage', array_merge($params, captionPayload($captionHtml)));
    if (!$res || empty($res['ok'])) {
        sendMessage($chatId, "❌ Qismni yuborishda xatolik yuz berdi. Birozdan so'ng qaytadan urinib ko'ring.");
        return;
    }
    $newMsgId = $res['result']['message_id'];

    $u = db()->prepare('UPDATE movies SET views_count = views_count + 1 WHERE id=?');
    $u->execute([$movieId]);

    if (!$vip) {
        incViewsToday($userId);
        $deleteAt = time() + 86400;
        $ins = db()->prepare('INSERT INTO movie_deliveries (movie_id, user_id, chat_id, message_id, delete_at, created_at) VALUES (?,?,?,?,?,?)');
        $ins->execute([$movieId, $userId, $chatId, $newMsgId, $deleteAt, time()]);
    }
}

function attemptDeliverMovie(int $userId, $chatId, string $code): void {
    $movie = findMovieByCode($code);
    if (!$movie) {
        sendMessage($chatId, "❌ Bunday kodli kino topilmadi. Kodni tekshirib qaytadan yuboring.");
        return;
    }
    $user = getUser($userId);
    if (!$user) { $user = upsertUser($userId, null, null); }

    if (($movie['access'] ?? 'all') === 'vip' && !isVipActive($user)) {
        sendMessage($chatId, "🌟 Bu kino faqat <b>VIP foydalanuvchilar</b> uchun mavjud.\n\n💎 VIP obunaga o'tib, ushbu va boshqa eksklyuziv kinolarni tomosha qiling!", ikb([[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]]));
        return;
    }

    if (!isVipActive($user)) {
        // 1) majburiy obuna tekshiruvi
        $missing = missingChannels($userId);
        if (!empty($missing)) {
            setState($userId, 'await_sub_then_movie', ['code' => $code]);
            sendSubscribePrompt($chatId, $missing, "🎬 Kinoni olish uchun quyidagi kanallarga obuna bo'ling, so'ng \"✅ Tekshirish\" tugmasini bosing:");
            return;
        }
        // 2) kunlik limit tekshiruvi
        $limit = dailyLimitFor($user);
        $used = getViewsToday($userId);
        if ($used >= getBonusToday($userId) + $limit) {
            $limitKb = [[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]];
            if ((int) getSetting('ad_bypass_enabled', 0) === 1 && findLimitBypassAd()) {
                $limitKb[] = [btn('🎥 Reklama ko\'rib, yana 1 ta kino ko\'ring', 'watch_ad_bypass:' . $code, 'success', emIcon('🎥'))];
            }
            sendMessage($chatId, "⛔️ Siz bugungi kunlik kino olish limitingizni ({$limit} ta) ishlatib bo'ldingiz.\n\nErtaga qaytadan urinib ko'ring yoki 💎 VIP obunaga o'ting — limitsiz tomosha qiling!", ikb($limitKb));
            return;
        }
        // 3) kino oldidan reklama (agar shu kino uchun faol reklama bo'lsa)
        $ad = findAdForMovie($code);
        if ($ad) showAdWithCountdown($chatId, $ad);
    }

    $vip = isVipActive($user);
    ensureBottomKeyboard($chatId, $userId);

    if (($movie['type'] ?? 'movie') === 'series') {
        clearState($userId);
        sendEpisodeList($chatId, (int) $movie['id'], null);
        return;
    }

    $captionHtml = "🎬 <b>" . h($movie['title']) . "</b>\n\n" . h($movie['description']);
    if (!$vip) {
        $captionHtml .= "\n\n⏳ Bu kino <b>24 soatdan</b> so'ng avtomatik o'chiriladi.\nO'chirilishini xohlamasangiz — 💎 VIP obunaga o'ting!";
    }

    $codesUrl = codesChannelUrl();
    $kbRows = [];
    if ($vip) {
        $kbRows[] = [btn('💾 Saqlash', 'save_movie:' . $movie['id'], 'success', emIcon('💾'))];
    } else {
        $kbRows[] = [btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())];
    }
    if ($codesUrl) {
        $kbRows[] = [ubtn('📡 Boshqa kinolar', $codesUrl, 'primary', emIcon('📡'))];
    }
    $kb = ikb($kbRows);

    $protect = (bool) (int) getSetting('copyright_protect', 1);

    $res = tgApi('copyMessage', array_merge([
        'chat_id' => $chatId,
        'from_chat_id' => storageChannelId(),
        'message_id' => $movie['storage_message_id'],
        'protect_content' => $protect,
        'reply_markup' => json_encode($kb),
    ], captionPayload($captionHtml)));

    if (!$res || empty($res['ok'])) {
        sendMessage($chatId, "❌ Kinoni yuborishda xatolik yuz berdi. Birozdan so'ng qaytadan urinib ko'ring.");
        return;
    }

    $newMsgId = $res['result']['message_id'];

    // statistika va kunlik limit
    $st = db()->prepare('UPDATE movies SET views_count = views_count + 1 WHERE id=?');
    $st->execute([$movie['id']]);

    if (!$vip) {
        incViewsToday($userId);
        // oddiy foydalanuvchiga yuborilgan kino 24 soatdan keyin o'chiriladi
        $deleteAt = time() + 86400;
        $ins = db()->prepare('INSERT INTO movie_deliveries (movie_id, user_id, chat_id, message_id, delete_at, created_at) VALUES (?,?,?,?,?,?)');
        $ins->execute([$movie['id'], $userId, $chatId, $newMsgId, $deleteAt, time()]);
    }

    clearState($userId);
}

/* ===================== 6) FOYDALANUVCHI MENYULARI ===================== */

function sendStartMenu($chatId): void {
    $text = getSetting('start_text', "✨ <b>Xush kelibsiz!</b> ✨\n\n🎬 Bu yerda minglab kinolarni his qilib tomosha qilishingiz mumkin.\n\nQuyidagilardan birini tanlang 👇");
    $photo = getSetting('start_photo', '');
    $kb = ikb([[btn('👍 Oddiy', 'menu_normal', 'primary', emIcon('👍')), btn('💎 VIP', 'menu_vip', 'primary', vipIcon())]]);
    if ($photo) {
        $p = array_merge(['chat_id' => $chatId, 'photo' => $photo, 'reply_markup' => json_encode($kb)], captionPayload($text));
        tgApi('sendPhoto', $p);
    } else {
        sendMessage($chatId, $text, $kb);
    }
}

// VIP yoki obunasi tasdiqlangan foydalanuvchiga "kino kodini yuborishingiz
// mumkin" xabari — matni/rasmi admin panelidan tahrirlanadi.
function vipRequiredMessage($chatId, string $feature): void {
    sendMessage($chatId, "🌟 <b>{$feature}</b> — bu funksiya faqat <b>VIP foydalanuvchilar</b> uchun.\n\n💎 VIP obunaga o'tib, bu va boshqa qulayliklardan foydalaning!", ikb([[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]]));
}

function showTop10($chatId, int $userId = 0): void {
    $user = $userId ? getUser($userId) : null;
    if ($userId && (!$user || !isVipActive($user))) { vipRequiredMessage($chatId, 'TOP 10 kinolar'); return; }
    $st = db()->query('SELECT code, title, views_count FROM movies ORDER BY views_count DESC LIMIT 10');
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "🏆 <b>TOP 10 kinolar</b>\n\n";
    if (empty($rows)) { $text .= "— hozircha kinolar yo'q —"; }
    $i = 1;
    foreach ($rows as $r) { $text .= "{$i}. " . h($r['title']) . " — kod: <code>" . h($r['code']) . "</code> ({$r['views_count']} marta)\n"; $i++; }
    sendMessage($chatId, $text);
}

function showMySaved($chatId, int $userId): void {
    $user = getUser($userId);
    if (!$user || !isVipActive($user)) { vipRequiredMessage($chatId, 'Saqlanganlarim'); return; }
    $st = db()->prepare('SELECT m.code, m.title, m.id FROM saved_movies sm JOIN movies m ON m.id = sm.movie_id WHERE sm.user_id=? ORDER BY sm.id DESC LIMIT 30');
    $st->execute([$userId]);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
    if (empty($rows)) { sendMessage($chatId, "🎞 Sizda hali saqlangan kino yo'q."); return; }
    $btnRows = [];
    foreach ($rows as $r) { $btnRows[] = [btn("🎬 " . $r['title'] . " (" . $r['code'] . ")", 'get_saved:' . $r['code'], 'primary', emIcon('🎬'))]; }
    sendMessage($chatId, "🎞 <b>Saqlangan kinolaringiz:</b>", ikb($btnRows));
}

// Status va Adminga murojaat kabi bo'limlar — VIP bo'lmagan foydalanuvchi
// uchun MAJBURIY kanallarga obuna bo'lmaguncha ishlamaydi (funksiyaning o'zi
// o'zgarmaydi, faqat oldiga obuna tekshiruvi qo'yiladi).
function ensureSubscribedForBasicFeature(int $userId, $chatId): bool {
    $user = getUser($userId);
    if ($user && isVipActive($user)) return true;
    $missing = missingChannels($userId);
    if (!empty($missing)) {
        setState($userId, 'await_sub_then_menu', []);
        sendSubscribePrompt($chatId, $missing, "📢 Bu bo'limdan foydalanish uchun avval quyidagi kanallarga obuna bo'ling, so'ng \"✅ Tekshirish\" tugmasini bosing:");
        return false;
    }
    return true;
}

function showMyStatus($chatId, int $userId): void {
    $user = getUser($userId);
    if ($user && isVipActive($user)) {
        $left = (int) $user['vip_until'] - time();
        $days = max(0, (int) floor($left / 86400));
        $hours = max(0, (int) floor(($left % 86400) / 3600));
        sendMessage($chatId, "📊 <b>Status</b>\n\n💎 Siz VIP foydalanuvchisiz.\n⏳ Muddati: <b>{$days} kun {$hours} soat</b> qoldi.");
    } else {
        $limit = $user ? dailyLimitFor($user) : DEFAULT_DAILY_LIMIT;
        $used = getViewsToday($userId);
        $text = "📊 <b>Status</b>\n\n🎬 Siz oddiy foydalanuvchisiz.\n📅 Kunlik ko'rish limitingiz: <b>{$used}/{$limit}</b>\n\n";
        $text .= "🌟 <b>VIP obuna sizga nima beradi?</b>\n";
        $text .= "• Kunlik limitsiz — istagancha kino\n";
        $text .= "• Kanallarga obuna bo'lish shart emas\n";
        $text .= "• Kinolar 24 soatda o'chmaydi\n";
        $text .= "• TOP 10, Saqlanganlarim kabi qulayliklar\n\n";
        $text .= "💎 Hoziroq VIP obunaga o'ting!";
        sendMessage($chatId, $text, ikb([[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]]));
    }
}

// Reply-keyboard (TOP10/Saqlanganlarim/Status/Support) faqat kerak bo'lganda
// (holat o'zgarganda) qayta yuboriladi — aks holda har safar qayta
// chiqaveradi. TOP 10 va Saqlanganlarim FAQAT VIP foydalanuvchiga ko'rsatiladi
// (chunki bu funksiyalar faqat VIP uchun) — shu bilan oddiy foydalanuvchi
// endi "bosilsa ham ishlamaydigan" tugmani umuman ko'rmaydi. Foydalanuvchi
// VIP bo'lgach klaviatura avtomatik yangilanib, TOP10/Saqlanganlarim ham
// qo'shiladi.
function ensureBottomKeyboard($chatId, int $userId): void {
    $user = getUser($userId);
    $vip = $user && isVipActive($user);
    $wanted = $vip ? 2 : 1; // 1 = oddiy (2 tugma), 2 = VIP (4 tugma)

    $st = db()->prepare('SELECT kb_shown FROM users WHERE telegram_id=?');
    $st->execute([$userId]);
    $shown = (int) $st->fetchColumn();
    if ($shown === $wanted) return; // allaqachon shu holat uchun ko'rsatilgan — qayta yubormaymiz

    if ($vip) {
        $rows = [
            [rkbBtn('🏆 TOP 10', 'primary'), rkbBtn('🎞 Saqlanganlarim', 'primary')],
            [rkbBtn('📊 Status', 'success'), rkbBtn('🧑‍💻 Adminga murojaat', 'danger', emIcon('🧑‍💻'))],
        ];
    } else {
        $rows = [
            [rkbBtn('📊 Status', 'success'), rkbBtn('🧑‍💻 Adminga murojaat', 'danger', emIcon('🧑‍💻'))],
        ];
    }
    $r = tgApi('sendMessage', ['chat_id' => $chatId, 'text' => '🎬', 'reply_markup' => json_encode(rkb($rows))]);
    if ($r && !empty($r['ok'])) {
        db()->prepare('UPDATE users SET kb_shown=? WHERE telegram_id=?')->execute([$wanted, $userId]);
    } else {
        @file_put_contents(__DIR__ . '/error.log', date('Y-m-d H:i:s') . ' ensureBottomKeyboard failed: ' . json_encode($r) . "\n", FILE_APPEND);
    }
}

function codesChannelUrl(): ?string {
    $codesId = codesChannelId();
    if (str_starts_with($codesId, '@')) return 'https://t.me/' . ltrim($codesId, '@');
    return null;
}

function sendCodePrompt($chatId, int $userId): void {
    $user = getUser($userId);
    $text = getSetting('code_prompt_text', "✅ Ajoyib!\n\n🎬 Endi istalgan kino kodini yuboring (masalan: <code>101</code>).");
    $photo = getSetting('code_prompt_photo', '');
    $codesUrl = codesChannelUrl();

    if ($user && !isVipActive($user)) {
        $limit = dailyLimitFor($user);
        $used = getViewsToday($userId);
        $text .= "\n\n📅 Bugungi limitingiz: <b>{$used}/{$limit}</b> ishlatildi.";
    }

    // Inline qatorda FAQAT kodlar kanali linki bo'ladi — boshqa hech narsa
    $kb = $codesUrl ? ikb([[ubtn('📡 Kodlar kanali', $codesUrl, 'primary', emIcon('📡'))]]) : null;

    if ($photo) {
        $p = array_merge(['chat_id' => $chatId, 'photo' => $photo], captionPayload($text));
        if ($kb) $p['reply_markup'] = json_encode($kb);
        tgApi('sendPhoto', $p);
    } else {
        sendMessage($chatId, $text, $kb);
    }

    // TOP10/Saqlanganlarim/Status/Support — hammaga button (reply-keyboard),
    // faqat bir marta yuboriladi, keyingi safarlarda qayta yuborilmaydi.
    ensureBottomKeyboard($chatId, $userId);
}

function handleMenuNormal(int $userId, $chatId): void {
    $user = getUser($userId);
    $sd = getStateData($user);
    $pendingCode = $sd['code'] ?? null;
    $missing = missingChannels($userId);
    if (!empty($missing)) {
        setState($userId, 'await_sub_then_menu', $pendingCode ? ['code' => $pendingCode] : []);
        sendSubscribePrompt($chatId, $missing, "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling, so'ng \"✅ Tekshirish\" tugmasini bosing:");
        return;
    }
    clearState($userId);
    if ($pendingCode) { attemptDeliverMovie($userId, $chatId, $pendingCode); return; }
    sendCodePrompt($chatId, $userId);
}

function handleMenuVip($chatId): void {
    $st = db()->query('SELECT * FROM vip_plans WHERE is_active=1 ORDER BY id');
    $plans = $st->fetchAll(PDO::FETCH_ASSOC);
    if (empty($plans)) {
        sendMessage($chatId, "Hozircha VIP rejalar mavjud emas. Birozdan so'ng qaytadan urinib ko'ring.");
        return;
    }
    $rows = [];
    foreach ($plans as $p) {
        $rows[] = [btn("💎 {$p['name']} — {$p['price']} so'm / {$p['duration_days']} kun", 'vip_plan:' . $p['id'], 'primary', vipIcon())];
    }
    sendMessage($chatId, "💎 VIP rejalardan birini tanlang:", ikb($rows));
}

// Sozlangan to'lov kartalari ro'yxati (Humo/Uzcard alohida, yoki eski yagona karta)
function getActiveCards(): array {
    $cards = [];
    $humo = getSetting('card_humo_number', '');
    if ($humo) $cards[] = ['method' => 'humo', 'label' => 'Humo', 'number' => $humo, 'owner' => getSetting('card_humo_owner', '')];
    $uzcard = getSetting('card_uzcard_number', '');
    if ($uzcard) $cards[] = ['method' => 'uzcard', 'label' => 'Uzcard', 'number' => $uzcard, 'owner' => getSetting('card_uzcard_owner', '')];
    if (empty($cards)) {
        $legacy = getSetting('payment_card', '');
        if ($legacy) $cards[] = ['method' => 'card', 'label' => "To'lov", 'number' => $legacy, 'owner' => getSetting('payment_card_owner', '')];
    }
    return $cards;
}

function findCardByMethod(string $method): ?array {
    foreach (getActiveCards() as $c) { if ($c['method'] === $method) return $c; }
    return null;
}

// Berilgan bazaviy narxga tasodifiy 1-99 so'm qo'shib, hozircha band qilinmagan
// noyob summa hosil qiladi (10 daqiqa davomida shu summa boshqa hech kimga berilmaydi)
function startVipPayment(int $userId, $chatId, int $planId): void {
    $cards = getActiveCards();
    if (empty($cards)) {
        sendMessage($chatId, "❌ Hozircha to'lov kartasi sozlanmagan. Pastdagi \"🧑‍💻 Adminga murojaat\" tugmasi orqali admin bilan bog'laning.");
        return;
    }
    if (count($cards) > 1) {
        $rows = [];
        foreach ($cards as $c) { $rows[] = [btn('💳 ' . $c['label'], 'pay_method:' . $c['method'] . ':' . $planId, 'primary', emIcon('💳'))]; }
        sendMessage($chatId, "💳 Qaysi karta orqali to'lamoqchisiz?", ikb($rows));
        return;
    }
    showPaymentAmount($userId, $chatId, $planId, $cards[0]['method']);
}

function showPaymentAmount(int $userId, $chatId, int $planId, string $method): void {
    $st = db()->prepare('SELECT * FROM vip_plans WHERE id=?');
    $st->execute([$planId]);
    $plan = $st->fetch(PDO::FETCH_ASSOC);
    if (!$plan) { sendMessage($chatId, '❌ Reja topilmadi.'); return; }
    $card = findCardByMethod($method);
    if (!$card) { sendMessage($chatId, "❌ Bu to'lov turi hozir mavjud emas."); return; }

    $exact = (int) preg_replace('/\D/', '', $plan['price']);

    $ins = db()->prepare("INSERT INTO vip_payments (user_id, plan_id, status, created_at, exact_amount, reserved_until, method) VALUES (?,?,'awaiting_payment',?,?,?,?)");
    $ins->execute([$userId, $planId, time(), $exact, time() + 600, $method]);
    $paymentId = (int) db()->lastInsertId();

    $text = "💎 <b>{$plan['name']}</b>\nMuddati: {$plan['duration_days']} kun\n\n";
    $text .= "💳 {$card['label']} karta: <code>" . h($card['number']) . "</code>\n";
    if ($card['owner']) $text .= "Karta egasi: " . h($card['owner']) . "\n";
    $text .= "\n💰 <b>Narxi:</b> <code>{$exact}</code> so'm\n";
    $text .= "⏳ Sizga <b>10 daqiqa</b> vaqt beriladi.\n\n";
    $text .= "To'lovni amalga oshirgach, pastdagi tugmani bosing.";

    sendMessage($chatId, $text, ikb([
        [btn('✅ To\'lov qildim', 'paid_confirm:' . $paymentId, 'success', emIcon('✅'))],
    ]));
}

/* ===================== 7) ADMIN PANEL ===================== */

// Barcha admin bo'limlariga kirish shu yerdan boshqariladi — shu tufayli
// bir xil bo'limni ham inline tugma orqali, ham pastdagi doimiy
// klaviatura (reply keyboard) tugmasi orqali ochish mumkin.
function admOpenSection(string $section, int $adminId, $chatId): void {
    $role = getRole($adminId);
    switch ($section) {
        case 'main': adminMainMenu($chatId, $adminId); break;
        case 'upload': admStartUpload($adminId, $chatId); break;
        case 'edit_movie':
            setState($adminId, 'admov_wait_code', []);
            sendMessage($chatId, "✏️ Tahrirlamoqchi bo'lgan kinoning kodini yuboring.");
            break;
        case 'stats': admStatsMenu($chatId); break;
        case 'channels': admChannelsList($chatId); break;
        case 'vip': admVipList($chatId); break;
        case 'premium': admPremiumMenu($chatId); break;
        case 'payment': admPaymentMenu($chatId); break;
        case 'limit':
            $cur = getSetting('daily_limit', DEFAULT_DAILY_LIMIT);
            $bypassOn = (int) getSetting('ad_bypass_enabled', 0) === 1;
            setState($adminId, 'adm_limit_wait', []);
            sendMessage($chatId, "Joriy kunlik limit: {$cur} ta.\nYangi qiymatni kiriting (yoki pastdagi tugmadan reklama orqali chetlab o'tishni yoqing/o'chiring).", ikb([
                [btn($bypassOn ? "🎥 Reklama orqali chetlab o'tish: YONIQ" : "🎥 Reklama orqali chetlab o'tish: O'CHIQ", 'toggle_ad_bypass', 'primary', emIcon('🎥'))],
            ]));
            break;
        case 'admins':
            if ($role === 'super') admAdminsList($chatId);
            else sendMessage($chatId, "⛔️ Bu bo'lim faqat super-adminlar uchun.");
            break;
        case 'broadcast':
            sendMessage($chatId, "📨 Xabarnoma turini tanlang:", ikb([
                [btn('↪️ Forward qilib yuborish', 'bc_mode:forward', 'primary', emIcon('↪️'))],
                [btn('✉️ Oddiy yuborish', 'bc_mode:normal', 'primary', emIcon('✉️'))],
            ]));
            break;
        case 'ads': admReklamaMenu($chatId); break;
        case 'edit_start':
            setState($adminId, 'adm_startmsg_wait_text', []);
            sendMessage($chatId, "✏️ /start xabarining yangi matnini yuboring (<b>...</b> va <code>...</code> teglaridan foydalansa bo'ladi).\n\nO'zgartirmasdan qoldirish uchun /skip yozing.");
            break;
        case 'edit_code':
            setState($adminId, 'adm_codemsg_wait_text', []);
            sendMessage($chatId, "✏️ \"Kino kodini yuborishingiz mumkin\" xabarining yangi matnini yuboring.\n\nO'zgartirmasdan qoldirish uchun /skip yozing.");
            break;
        case 'edit_expired':
            setState($adminId, 'adm_expmsg_wait_text', []);
            sendMessage($chatId, "✏️ Kino 24 soatdan keyin o'chgach ko'rinadigan xabarning yangi matnini yuboring.\n\nO'zgartirmasdan qoldirish uchun /skip yozing.");
            break;
        case 'copyright':
            $cur = (int) getSetting('copyright_protect', 1);
            $new = $cur ? 0 : 1;
            setSetting('copyright_protect', (string) $new);
            sendMessage($chatId, $new
                ? "©️ Mualliflik huquqi himoyasi YONDI.\nEndi kinolarni forward qilib yoki galereyaga saqlab bo'lmaydi."
                : "©️ Mualliflik huquqi himoyasi O'CHDI.\nEndi kinolarni forward qilish va saqlash mumkin bo'ladi.");
            break;
        case 'emoji_pack': admEmojiPackMenu($chatId); break;
    }
}

function admEmojiPackMenu($chatId): void {
    $map = emojiMap();
    $text = "🎨 <b>Premium emoji</b>\n\nQaysi emojini tahrirlamoqchisiz? Tanlang:\n\n";
    $rows = [];
    $line = [];
    $i = 0;
    foreach ($map as $emoji => $id) {
        $line[] = btn($emoji, 'emoji_edit:' . $emoji, 'primary');
        $i++;
        if ($i % 6 === 0) { $rows[] = $line; $line = []; }
    }
    if (!empty($line)) $rows[] = $line;
    $rows[] = [btn('➕ Yangi emoji qo\'shish', 'emoji_add', 'success', emIcon('➕'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

function rkb(array $rows): array {
    $kb = [];
    foreach ($rows as $r) {
        $line = [];
        foreach ($r as $t) {
            if (is_array($t)) { $line[] = $t; }
            else { $line[] = ['text' => $t]; }
        }
        $kb[] = $line;
    }
    return ['keyboard' => $kb, 'resize_keyboard' => true, 'is_persistent' => true];
}
function rkbBtn(string $text, ?string $style = null, ?string $icon = null): array {
    if ($icon && USE_PREMIUM_EMOJI) { $b = ['text' => stripLeadingEmoji($text), 'icon_custom_emoji_id' => $icon]; }
    else { $b = ['text' => $text]; }
    if ($style) $b['style'] = $style;
    return $b;
}

// Reply-keyboard tugma matni -> admOpenSection bo'lim nomi
function adminMenuLabelMap(): array {
    return [
        '📤 Kino va serial yuklash' => 'upload',
        '✏️ Kino/serial tahrirlash' => 'edit_movie',
        '📊 Statistika' => 'stats',
        '📨 Xabarnoma' => 'broadcast',
        '📢 Reklama' => 'ads',
        '📡 Kanallar va linklar' => 'channels',
        '💎 VIP rejalar' => 'vip',
        '🌟 Premium foydalanuvchilar' => 'premium',
        '💳 To\'lov karta' => 'payment',
        '⏳ Kunlik limit' => 'limit',
        '✏️ Start xabari' => 'edit_start',
        '✏️ Kod xabari' => 'edit_code',
        "🖼 O'chirilgan kino xabari" => 'edit_expired',
        '©️ Mualliflik huquqi' => 'copyright',
        '🎨 Premium emoji' => 'emoji_pack',
        '🛠 Adminlar' => 'admins',
    ];
}

function adminMainMenu($chatId, int $adminId): void {
    $role = getRole($adminId);
    $rows = [
        ['📤 Kino va serial yuklash', '✏️ Kino/serial tahrirlash'],
        ['📊 Statistika', '📨 Xabarnoma'],
        ['📢 Reklama', '📡 Kanallar va linklar'],
        ['💎 VIP rejalar', '🌟 Premium foydalanuvchilar'],
        ['💳 To\'lov karta', '⏳ Kunlik limit'],
        ['©️ Mualliflik huquqi', '🎨 Premium emoji'],
        ['✏️ Start xabari', '✏️ Kod xabari'],
        ["🖼 O'chirilgan kino xabari"],
    ];
    if ($role === 'super') $rows[] = ['🛠 Adminlar'];
    $rows[] = ['⬅️ Panelni yopish'];
    sendMessage($chatId, "🛠 <b>Admin panel</b>\n\nKerakli bo'limni tanlang 👇", rkb($rows));
}

/* ---- 7.1 Kino yuklash ---- */

function admStartUpload(int $adminId, $chatId): void {
    setState($adminId, 'up_wait_type', []);
    sendMessage($chatId, "🎬 Nimani yuklamoqchisiz?", ikb([
        [btn('🎬 Kino', 'up_type:movie', 'primary', emIcon('🎬')), btn('📺 Serial', 'up_type:series', 'primary', emIcon('🎬'))],
    ]));
}

function handleUploadFlow(array $admin, array $msg): void {
    $adminId = (int) $admin['telegram_id'];
    $chatId = $msg['chat']['id'];
    $state = $admin['state'];
    $data = getStateData($admin);

    if ($state === 'up_wait_movie') {
        if (!isset($msg['video']) && !isset($msg['document']) && !isset($msg['animation'])) {
            sendMessage($chatId, "❌ Iltimos, video yoki fayl ko'rinishida kino yuboring.");
            return;
        }
        $copy = tgApi('copyMessage', [
            'chat_id' => storageChannelId(),
            'from_chat_id' => $chatId,
            'message_id' => $msg['message_id'],
        ]);
        if (!$copy || empty($copy['ok'])) {
            sendMessage($chatId, "❌ Kinoni bazaga saqlashda xatolik. Bot kinolar bazasi kanalida admin ekanini tekshiring.");
            return;
        }
        $data['storage_message_id'] = $copy['result']['message_id'];
        setState($adminId, 'up_wait_intro', $data);
        sendMessage($chatId, "🎞 Endi shu kino uchun intro/prevyu (qisqa video yoki rasm) yuboring.\nAgar prevyu bo'lmasa, /skip deb yozing.");
        return;
    }

    if ($state === 'up_wait_intro') {
        if (isset($msg['text']) && trim($msg['text']) === '/skip') {
            $data['intro'] = null;
        } elseif (isset($msg['video'])) {
            $data['intro'] = ['type' => 'video', 'file_id' => $msg['video']['file_id']];
        } elseif (isset($msg['photo'])) {
            $photos = $msg['photo'];
            $data['intro'] = ['type' => 'photo', 'file_id' => end($photos)['file_id']];
        } else {
            sendMessage($chatId, "❌ Video yoki rasm yuboring, yoki /skip deb yozing.");
            return;
        }
        setState($adminId, 'up_wait_code', $data);
        sendMessage($chatId, "🔢 Endi kino kodini (raqam) yuboring.");
        return;
    }

    if ($state === 'up_wait_code') {
        $code = trim($msg['text'] ?? '');
        if ($code === '' || findMovieByCode($code)) {
            sendMessage($chatId, "❌ Bu kod bo'sh yoki band. Boshqa kod yuboring.");
            return;
        }
        $data['code'] = $code;
        // bazaga saqlangan faylning tagiga kino kodini yozib qo'yamiz
        if (!empty($data['storage_message_id'])) {
            $epLabel = ($data['type'] ?? 'movie') === 'series' ? ' | 1-qism' : '';
            tgApi('sendMessage', ['chat_id' => storageChannelId(), 'reply_to_message_id' => $data['storage_message_id'], 'text' => "🔑 Kino kodi: {$code}{$epLabel}"]);
        }
        setState($adminId, 'up_wait_title', $data);
        sendMessage($chatId, "📝 Endi kino nomini yuboring.");
        return;
    }

    if ($state === 'up_wait_title') {
        $title = trim($msg['text'] ?? '');
        if ($title === '') { sendMessage($chatId, '❌ Nom bo\'sh bo\'lmasin.'); return; }
        $data['title'] = $title;
        setState($adminId, 'up_wait_desc', $data);
        sendMessage($chatId, "📄 Endi kino tavsifini yuboring.");
        return;
    }

    if ($state === 'up_wait_desc') {
        $desc = trim($msg['text'] ?? '');
        $data['description'] = $desc;
        setState($adminId, 'up_wait_access', $data);
        sendMessage($chatId, "👥 Bu kino/serial kimlar uchun?", ikb([
            [btn('👥 Barcha uchun', 'up_access:all', 'primary'), btn('🌟 Faqat VIP uchun', 'up_access:vip', 'primary', vipIcon())],
        ]));
        return;
    }

    // ---- Serial: yangi qism (davomiy yuklash) ----
    if ($state === 'up_series_wait_ep') {
        if (!isset($msg['video']) && !isset($msg['document']) && !isset($msg['animation'])) {
            sendMessage($chatId, "❌ Iltimos, video yoki fayl ko'rinishida qism yuboring.");
            return;
        }
        $copy = tgApi('copyMessage', [
            'chat_id' => storageChannelId(),
            'from_chat_id' => $chatId,
            'message_id' => $msg['message_id'],
        ]);
        if (!$copy || empty($copy['ok'])) {
            sendMessage($chatId, "❌ Bazaga saqlashda xatolik. Bot kinolar bazasi kanalida admin ekanini tekshiring.");
            return;
        }
        $epNum = (int) ($data['next_ep'] ?? 2);
        $epIns = db()->prepare('INSERT INTO episodes (movie_id, ep_number, storage_message_id, created_at) VALUES (?,?,?,?)');
        $epIns->execute([$data['movie_id'], $epNum, $copy['result']['message_id'], time()]);
        tgApi('sendMessage', ['chat_id' => storageChannelId(), 'reply_to_message_id' => $copy['result']['message_id'], 'text' => "🔑 Kino kodi: {$data['code']} | {$epNum}-qism"]);

        $data['next_ep'] = $epNum + 1;
        setState($adminId, 'up_series_more', $data);
        sendMessage($chatId, "✅ {$epNum}-qism saqlandi.\n\nYana qism qo'shasizmi?", ikb([
            [btn('➕ Yana qism qo\'shish', 'series_addmore', 'success', emIcon('➕'))],
            [btn('✅ Post qilish (tugatish)', 'series_publish', 'primary', emIcon('✅'))],
        ]));
        return;
    }

    // ---- Kino tahrirlash: mavjud serialga yangi qism qo'shish ----
    if ($state === 'admov_wait_newep') {
        if (!isset($msg['video']) && !isset($msg['document']) && !isset($msg['animation'])) {
            sendMessage($chatId, "❌ Iltimos, video yoki fayl ko'rinishida qism yuboring.");
            return;
        }
        $copy = tgApi('copyMessage', [
            'chat_id' => storageChannelId(),
            'from_chat_id' => $chatId,
            'message_id' => $msg['message_id'],
        ]);
        if (!$copy || empty($copy['ok'])) {
            sendMessage($chatId, "❌ Bazaga saqlashda xatolik. Bot kinolar bazasi kanalida admin ekanini tekshiring.");
            return;
        }
        $epNum = (int) $data['next_ep'];
        $epIns = db()->prepare('INSERT INTO episodes (movie_id, ep_number, storage_message_id, created_at) VALUES (?,?,?,?)');
        $epIns->execute([$data['movie_id'], $epNum, $copy['result']['message_id'], time()]);
        $movieForCode = findMovieById((int) $data['movie_id']);
        $mcode = $movieForCode['code'] ?? '';
        tgApi('sendMessage', ['chat_id' => storageChannelId(), 'reply_to_message_id' => $copy['result']['message_id'], 'text' => "🔑 Kino kodi: {$mcode} | {$epNum}-qism"]);
        clearState($adminId);
        sendMessage($chatId, "✅ {$epNum}-qism muvaffaqiyatli qo'shildi.");
        return;
    }
}

function finalizeMovieUpload(int $adminId, $chatId, array $data, string $access): void {
    $desc = $data['description'];
    $ins = db()->prepare('INSERT INTO movies (code, title, description, storage_message_id, added_by, created_at, access) VALUES (?,?,?,?,?,?,?)');
    $ins->execute([$data['code'], $data['title'], $desc, $data['storage_message_id'], $adminId, time(), $access]);

    $deepLink = 'https://t.me/' . BOT_USERNAME . '?start=movie_' . urlencode($data['code']);
    $shareLink = 'https://t.me/share/url?url=' . urlencode($deepLink) . '&text=' . urlencode($data['title']);

    $accessLabel = $access === 'vip' ? "\n\n🌟 <b>Faqat VIP foydalanuvchilar uchun</b>" : "\n\n👥 <b>Barcha foydalanuvchilar uchun</b>";
    $caption = "🎬 <b>" . h($data['title']) . "</b>\n\n" . h($desc) . $accessLabel . "\n\n🔑 Kino kodi: <code>" . h($data['code']) . "</code>";
    $kb = ikb([
        [ubtn("✈️ Do'stlarga ulashish", $shareLink, 'success', emIcon('✈️'))],
        [ubtn('📥 Kino yuklash', $deepLink, 'primary', emIcon('📥'))],
    ]);

    if (!empty($data['intro']) && $data['intro']['type'] === 'video') {
        tgApi('sendVideo', array_merge(['chat_id' => codesChannelId(), 'video' => $data['intro']['file_id'], 'reply_markup' => json_encode($kb)], captionPayload($caption)));
    } elseif (!empty($data['intro']) && $data['intro']['type'] === 'photo') {
        tgApi('sendPhoto', array_merge(['chat_id' => codesChannelId(), 'photo' => $data['intro']['file_id'], 'reply_markup' => json_encode($kb)], captionPayload($caption)));
    } else {
        tgApi('sendMessage', array_merge(['chat_id' => codesChannelId(), 'reply_markup' => json_encode($kb)], textPayload($caption)));
    }

    clearState($adminId);
    sendMessage($chatId, "✅ Kino muvaffaqiyatli qo'shildi va kanalga joylandi!");
}

/* ---- 7.1b Serial yuklash (1-qism yakunlanganda) ---- */

function finalizeSeriesUpload(int $adminId, $chatId, array $data, string $access): void {
    $desc = $data['description'];
    $ins = db()->prepare("INSERT INTO movies (code, title, description, storage_message_id, added_by, created_at, access, type) VALUES (?,?,?,?,?,?,?,'series')");
    $ins->execute([$data['code'], $data['title'], $desc, $data['storage_message_id'], $adminId, time(), $access]);
    $movieId = (int) db()->lastInsertId();

    $epIns = db()->prepare('INSERT INTO episodes (movie_id, ep_number, storage_message_id, created_at) VALUES (?,?,?,?)');
    $epIns->execute([$movieId, 1, $data['storage_message_id'], time()]);

    $seriesData = [
        'movie_id' => $movieId,
        'code' => $data['code'],
        'title' => $data['title'],
        'description' => $desc,
        'access' => $access,
        'intro' => $data['intro'] ?? null,
        'next_ep' => 2,
    ];
    setState($adminId, 'up_series_more', $seriesData);
    sendMessage($chatId, "✅ 1-qism saqlandi.\n\nYana qism qo'shasizmi yoki shu bilan postni chop qilaymi?", ikb([
        [btn('➕ Yana qism qo\'shish', 'series_addmore', 'success', emIcon('➕'))],
        [btn('✅ Post qilish (tugatish)', 'series_publish', 'primary', emIcon('✅'))],
    ]));
}

// Serial haqidagi post kodlar kanaliga chop etiladi (barcha qismlar bitta kodga bog'liq bo'ladi)
function publishSeriesPost(int $adminId, $chatId, array $data): void {
    $movieId = (int) $data['movie_id'];
    $epCount = count(movieEpisodes($movieId));

    $deepLink = 'https://t.me/' . BOT_USERNAME . '?start=movie_' . urlencode($data['code']);
    $shareLink = 'https://t.me/share/url?url=' . urlencode($deepLink) . '&text=' . urlencode($data['title']);

    $accessLabel = $data['access'] === 'vip' ? "\n\n🌟 <b>Faqat VIP foydalanuvchilar uchun</b>" : "\n\n👥 <b>Barcha foydalanuvchilar uchun</b>";
    $caption = "📺 <b>" . h($data['title']) . "</b>\n\n" . h($data['description']) . $accessLabel . "\n\n🎞 Qismlar soni: {$epCount} ta\n🔑 Kino kodi: <code>" . h($data['code']) . "</code>";
    $kb = ikb([
        [ubtn("✈️ Do'stlarga ulashish", $shareLink, 'success', emIcon('✈️'))],
        [ubtn('📥 Yuklab olish', $deepLink, 'primary', emIcon('📥'))],
    ]);

    $intro = $data['intro'] ?? null;
    if (!empty($intro) && $intro['type'] === 'video') {
        tgApi('sendVideo', array_merge(['chat_id' => codesChannelId(), 'video' => $intro['file_id'], 'reply_markup' => json_encode($kb)], captionPayload($caption)));
    } elseif (!empty($intro) && $intro['type'] === 'photo') {
        tgApi('sendPhoto', array_merge(['chat_id' => codesChannelId(), 'photo' => $intro['file_id'], 'reply_markup' => json_encode($kb)], captionPayload($caption)));
    } else {
        tgApi('sendMessage', array_merge(['chat_id' => codesChannelId(), 'reply_markup' => json_encode($kb)], textPayload($caption)));
    }

    clearState($adminId);
    sendMessage($chatId, "✅ Serial muvaffaqiyatli qo'shildi va kanalga joylandi! Jami {$epCount} ta qism.");
}

/* ---- 7.2 Statistika ---- */

function periodLabel(string $p): string {
    return ['1h' => '1 soat', '24h' => '24 soat', 'week' => 'Hafta', 'month' => 'Oy', 'year' => 'Yil'][$p] ?? $p;
}
function periodSeconds(string $p): int {
    return ['1h' => 3600, '24h' => 86400, 'week' => 604800, 'month' => 2592000, 'year' => 31536000][$p] ?? 86400;
}

function admStatsMenu($chatId): void {
    $kb = ikb([
        [btn('👤 Foydalanuvchilar', 'adm_stats_u', 'primary', emIcon('👤'))],
        [btn('📡 Kanallar', 'adm_stats_c', 'primary', emIcon('📡'))],
        [btn('🎬 Kinolar', 'adm_stats_m', 'primary', emIcon('🎬'))],
        [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))],
    ]);
    sendMessage($chatId, "📊 Statistika bo'limi:", $kb);
}

function admStatsUsersPeriods($chatId, $messageId = null): void {
    $rows = [];
    foreach (['1h', '24h', 'week', 'month', 'year'] as $p) {
        $rows[] = [btn(periodLabel($p), 'adm_su:' . $p)];
    }
    $rows[] = [btn('⬅️ Orqaga', 'adm_stats', null, emIcon('⬅️'))];
    $text = "👤 Davrni tanlang:";
    if ($messageId) editMessageText($chatId, $messageId, $text, ikb($rows));
    else sendMessage($chatId, $text, ikb($rows));
}

function admStatsUsersShow($chatId, $messageId, string $period): void {
    $since = time() - periodSeconds($period);
    $st = db()->prepare('SELECT COUNT(*) FROM users WHERE joined_at >= ?');
    $st->execute([$since]);
    $joined = (int) $st->fetchColumn();

    $st2 = db()->prepare("SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event='blocked' AND created_at >= ?");
    $st2->execute([$since]);
    $blocked = (int) $st2->fetchColumn();

    $st3 = db()->query('SELECT COUNT(*) FROM users');
    $total = (int) $st3->fetchColumn();

    $text = "👤 <b>Foydalanuvchilar statistikasi</b> (" . periodLabel($period) . ")\n\n";
    $text .= "➕ Yangi qo'shilganlar: <b>{$joined}</b>\n";
    $text .= "➖ Botni o'chirganlar: <b>{$blocked}</b>\n\n";
    $text .= "👥 Jami foydalanuvchilar: <b>{$total}</b>";

    editMessageText($chatId, $messageId, $text, ikb([[btn('⬅️ Orqaga', 'adm_stats_u', null, emIcon('⬅️'))]]));
}

function admStatsChannelsList($chatId, $messageId = null): void {
    $st = db()->query('SELECT * FROM channels ORDER BY id');
    $chs = $st->fetchAll(PDO::FETCH_ASSOC);
    if (empty($chs)) {
        $text = "Hozircha kanallar qo'shilmagan.";
        if ($messageId) editMessageText($chatId, $messageId, $text, ikb([[btn('⬅️ Orqaga', 'adm_stats', null, emIcon('⬅️'))]]));
        else sendMessage($chatId, $text);
        return;
    }
    $rows = [];
    foreach ($chs as $c) { $rows[] = [btn($c['title'], 'adm_sc:' . $c['id'] . ':24h')]; }
    $rows[] = [btn('⬅️ Orqaga', 'adm_stats')];
    $text = "📡 Kanalni tanlang:";
    if ($messageId) editMessageText($chatId, $messageId, $text, ikb($rows));
    else sendMessage($chatId, $text, ikb($rows));
}

function admStatsChannelShow($chatId, $messageId, int $chId, string $period): void {
    $st = db()->prepare('SELECT * FROM channels WHERE id=?');
    $st->execute([$chId]);
    $ch = $st->fetch(PDO::FETCH_ASSOC);
    if (!$ch) return;

    $since = time() - periodSeconds($period);
    $st2 = db()->prepare("SELECT COUNT(*) FROM channel_events WHERE channel_db_id=? AND action='subscribed' AND created_at>=?");
    $st2->execute([$chId, $since]);
    $subs = (int) $st2->fetchColumn();

    $rows = [];
    foreach (['1h', '24h', 'week', 'month', 'year'] as $p) {
        $mark = $p === $period ? '• ' : '';
        $rows[] = [btn($mark . periodLabel($p), 'adm_sc:' . $chId . ':' . $p)];
    }
    $rows[] = [btn('⬅️ Orqaga', 'adm_stats_c', null, emIcon('⬅️'))];

    $text = "📡 <b>" . h($ch['title']) . "</b> (" . periodLabel($period) . ")\n\nObuna bo'lganlar / so'rov yuborganlar: <b>{$subs}</b>";
    editMessageText($chatId, $messageId, $text, ikb($rows));
}

function admStatsMoviesShow($chatId, $messageId = null): void {
    $st = db()->query('SELECT code, title, views_count FROM movies ORDER BY views_count DESC LIMIT 30');
    $movies = $st->fetchAll(PDO::FETCH_ASSOC);
    if (empty($movies)) {
        $text = "Hozircha kinolar qo'shilmagan.";
    } else {
        $text = "🎬 <b>Kinolar statistikasi</b> (eng ko'p ko'rilganlar):\n\n";
        foreach ($movies as $m) {
            $text .= "🔑 " . h($m['code']) . " — " . h($m['title']) . " — <b>{$m['views_count']}</b> marta\n";
        }
    }
    $kb = ikb([[btn('⬅️ Orqaga', 'adm_stats', null, emIcon('⬅️'))]]);
    if ($messageId) editMessageText($chatId, $messageId, $text, $kb);
    else sendMessage($chatId, $text, $kb);
}

/* ---- 7.3 Majburiy kanallar ---- */

function channelTypeLabel(string $type): string {
    return [
        'public' => 'Ommaviy kanal',
        'private_sub' => 'Maxfiy kanal (link orqali obuna)',
        'private_request' => "Maxfiy kanal (qo'shilish so'rovi)",
        'optional' => 'Ixtiyoriy link',
    ][$type] ?? $type;
}

function channelTypeDescription(string $type): string {
    return [
        'public' => "👥 <b>Ommaviy kanal</b> — kanalning ochiq @username'i bo'ladi. Bot foydalanuvchining shu kanalga obuna ekanini avtomatik tekshiradi (getChatMember). Faqat @username kerak bo'ladi.",
        'private_sub' => "🔒 <b>Maxfiy kanal — link orqali obuna</b> — kanal yopiq (username yo'q), lekin taklif linki orqali kirilgach darhol a'zo bo'ladi. Bot obunani avtomatik tekshiradi. Kanal ID raqami VA taklif linki kerak bo'ladi.",
        'private_request' => "📨 <b>Maxfiy kanal — qo'shilish so'rovi</b> — kanal yopiq va taklif linki \"so'rov yuborish\" turida (admin tasdiqlashi kerak bo'lgan link). Bot foydalanuvchi so'rov yuborganini avtomatik payqaydi va shuni yetarli deb hisoblaydi (qo'shimcha tekshiruv yoki ID so'ralmaydi). Kanal ID raqami VA so'rovli taklif linki kerak bo'ladi.",
        'optional' => "🔗 <b>Ixtiyoriy link</b> — bu majburiy emas, shunchaki qo'shimcha tugma sifatida obuna ro'yxati tagida ko'rsatiladi (masalan reklama yoki sayt havolasi). Faqat tugma nomi va link kerak bo'ladi.",
    ][$type] ?? '';
}

function admChannelsList($chatId): void {
    $st = db()->query('SELECT * FROM channels ORDER BY id');
    $chs = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "📡 <b>Kanallar va linklar:</b>\n\n";
    $text .= "🎬 Kino baza kanali: <code>" . h(storageChannelId()) . "</code>\n";
    $text .= "🔑 Kino kodlari kanali: <code>" . h(codesChannelId()) . "</code>\n\n";
    $text .= "<b>Majburiy obuna kanallari:</b>\n";
    $rows = [];
    if (empty($chs)) $text .= "— hozircha qo'shilmagan —\n";
    foreach ($chs as $c) {
        $text .= "• " . h($c['title']) . " — " . channelTypeLabel($c['type']) . "\n";
        $rows[] = [btn("❌ O'chirish: " . $c['title'], 'adm_ch_del:' . $c['id'], 'danger', emIcon('❌'))];
    }
    $rows[] = [btn('✏️ Kino baza kanalini tahrirlash', 'adm_ch_edit:storage', 'primary', emIcon('✏️'))];
    $rows[] = [btn('✏️ Kino kodlari kanalini tahrirlash', 'adm_ch_edit:codes', 'primary', emIcon('✏️'))];
    $rows[] = [btn('➕ Ommaviy kanal', 'adm_ch_add:public', 'success', emIcon('➕')), btn('➕ Maxfiy kanal 1 (so\'rov)', 'adm_ch_add:private_request', 'success', emIcon('➕'))];
    $rows[] = [btn('➕ Maxfiy kanal 2 (link)', 'adm_ch_add:private_sub', 'success', emIcon('➕')), btn('➕ Ixtiyoriy link', 'adm_ch_add:optional', 'success', emIcon('➕'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

function admChannelDelete(int $id): void {
    $st = db()->prepare('DELETE FROM channels WHERE id=?');
    $st->execute([$id]);
}

/* ---- 7.4 VIP rejalar ---- */

/* ---- 7.0b Kino oldi reklama ---- */

function finalizeAd(int $adminId, $chatId, array $data, string $codes): void {
    $ins = db()->prepare('INSERT INTO ads (content_type, text, file_id, button_text, button_url, duration_seconds, target_codes, purpose, mode, forward_chat_id, forward_message_id, is_active, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)');
    $ins->execute([
        $data['content_type'] ?? null,
        $data['text'] ?? '',
        $data['file_id'] ?? null,
        $data['button_text'] ?? null,
        $data['button_url'] ?? null,
        $data['duration_seconds'] ?? 10,
        trim($codes) !== '' ? trim($codes) : 'all',
        $data['purpose'] ?? 'movie',
        $data['mode'] ?? 'normal',
        $data['forward_chat_id'] ?? null,
        $data['forward_message_id'] ?? null,
        time(),
    ]);
    clearState($adminId);
    sendMessage($chatId, "✅ Reklama qo'shildi.");
    admAdsList($chatId, ($data['purpose'] ?? 'movie') === 'limit_bypass' ? 'limit_bypass' : 'movie');
}

function admAdsList($chatId, ?string $purposeFilter = null): void {
    if ($purposeFilter !== null) {
        $st = db()->prepare('SELECT * FROM ads WHERE purpose=? ORDER BY id DESC');
        $st->execute([$purposeFilter]);
    } else {
        $st = db()->query('SELECT * FROM ads ORDER BY id DESC');
    }
    $ads = $st->fetchAll(PDO::FETCH_ASSOC);
    $title = $purposeFilter === 'limit_bypass' ? "⏳ <b>Limitni chetlash reklamalari</b>" : ($purposeFilter === 'movie' ? "🎬 <b>Kino oldi reklamalari</b>" : "🎥 <b>Barcha reklamalar</b>");
    $text = $title . "\n\n";
    $rows = [];
    if (empty($ads)) {
        $text .= "— hozircha qo'shilmagan —\n";
    } else {
        foreach ($ads as $a) {
            $state = $a['is_active'] ? '🟢' : '⚪️';
            $purposeLabel = ($a['purpose'] ?? 'movie') === 'limit_bypass' ? '⏳ limit uchun' : '🎬 kino uchun';
            $modeLabel = ($a['mode'] ?? 'normal') === 'forward' ? '↪️ forward' : '✉️ oddiy';
            $text .= "{$state} #{$a['id']} — {$purposeLabel} — {$modeLabel} — {$a['duration_seconds']}s — kodlar: {$a['target_codes']}\n";
            $toggleIcon = $a['is_active'] ? emIcon('⏸') : emIcon('▶️');
            $rows[] = [
                btn("✏️ #{$a['id']}", 'ad_edit:' . $a['id'], 'primary', emIcon('✏️')),
                btn(($a['is_active'] ? '⏸' : '▶️') . " #{$a['id']}", 'ad_toggle:' . $a['id'], 'primary', $toggleIcon),
                btn("🗑 #{$a['id']}", 'ad_del:' . $a['id'], 'danger', emIcon('🗑')),
            ];
        }
    }
    if ($purposeFilter === 'limit_bypass') {
        $rows[] = [btn('➕ Reklama qo\'shish', 'ad_add:limit_bypass', 'success', emIcon('➕'))];
        $rows[] = [btn('⬅️ Orqaga', 'adm_ads_menu', null, emIcon('⬅️'))];
    } elseif ($purposeFilter === 'movie') {
        $rows[] = [btn('➕ Reklama qo\'shish', 'ad_add:movie', 'success', emIcon('➕'))];
        $rows[] = [btn('⬅️ Orqaga', 'adm_ads_menu', null, emIcon('⬅️'))];
    } else {
        $rows[] = [btn('➕ Kino uchun reklama', 'ad_add:movie', 'success', emIcon('➕')), btn('➕ Limitni chetlab o\'tish uchun', 'ad_add:limit_bypass', 'success', emIcon('➕'))];
        $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
    }
    sendMessage($chatId, $text, ikb($rows));
}

function admReklamaMenu($chatId): void {
    $text = "📢 <b>Reklama bo'limi</b>\n\nQaysi turdagi reklamani boshqarmoqchisiz?";
    $rows = [
        [btn('🎬 Kino oldi reklama', 'adm_ads_movie', 'primary', emIcon('🎬'))],
        [btn('⏳ Limitni chetlash reklama', 'adm_ads_limit', 'primary', emIcon('⏳'))],
        [btn('📡 Kanalga yuboriluvchi reklama', 'adm_chads_menu', 'primary', emIcon('📡'))],
        [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))],
    ];
    sendMessage($chatId, $text, ikb($rows));
}

/* ===================== 7c) KANALGA YUBORILUVCHI REKLAMA ===================== */

function finalizeChannelAd(int $adminId, $chatId, array $data): void {
    $ins = db()->prepare('INSERT INTO channel_ads (promo_channel_id, ad_mode, content_mode, content_type, text, file_id, button_text, button_url, forward_chat_id, forward_message_id, delay_minutes, requeue_minutes, auto_delete_prev, times_json, is_active, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?,1,?)');
    $ins->execute([
        $data['promo_channel_id'],
        $data['ad_mode'],
        $data['content_mode'] ?? 'normal',
        $data['content_type'] ?? null,
        $data['text'] ?? '',
        $data['file_id'] ?? null,
        $data['button_text'] ?? null,
        $data['button_url'] ?? null,
        $data['forward_chat_id'] ?? null,
        $data['forward_message_id'] ?? null,
        $data['delay_minutes'] ?? 30,
        $data['requeue_minutes'] ?? 60,
        json_encode($data['times'] ?? []),
        time(),
    ]);
    clearState($adminId);
    sendMessage($chatId, "✅ Reklama qo'shildi.");
    admChAdsChannelMenu($chatId, (int) $data['promo_channel_id']);
}

function admChAdsMenu($chatId): void {
    $st = db()->query('SELECT * FROM promo_channels ORDER BY id');
    $chs = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "📡 <b>Kanalga yuboriluvchi reklama</b>\n\nSozlangan kanallar:\n\n";
    $rows = [];
    if (empty($chs)) {
        $text .= "— hozircha qo'shilmagan —\n";
    } else {
        foreach ($chs as $c) {
            $state = $c['is_active'] ? '🟢' : '⚪️';
            $text .= "{$state} " . h($c['title']) . "\n";
            $rows[] = [btn('⚙️ ' . $c['title'], 'chad_ch:' . $c['id'], 'primary')];
        }
    }
    $rows[] = [btn('➕ Kanal qo\'shish', 'chad_ch_add', 'success', emIcon('➕'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_ads_menu', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

function admChAdsChannelMenu($chatId, int $pcId): void {
    $st = db()->prepare('SELECT * FROM promo_channels WHERE id=?');
    $st->execute([$pcId]);
    $pc = $st->fetch(PDO::FETCH_ASSOC);
    if (!$pc) { sendMessage($chatId, "❌ Topilmadi."); return; }

    $top = db()->prepare("SELECT * FROM channel_ads WHERE promo_channel_id=? AND ad_mode='top_post' ORDER BY id");
    $top->execute([$pcId]);
    $topAds = $top->fetchAll(PDO::FETCH_ASSOC);

    $sch = db()->prepare("SELECT * FROM channel_ads WHERE promo_channel_id=? AND ad_mode='scheduled' ORDER BY id");
    $sch->execute([$pcId]);
    $schAds = $sch->fetchAll(PDO::FETCH_ASSOC);

    $text = "⚙️ <b>" . h($pc['title']) . "</b>\n\n";
    $text .= "🔝 Top post reklamalari: " . count($topAds) . " ta\n";
    $text .= "🕐 Vaqtli reklamalar: " . count($schAds) . " ta\n";

    $rows = [];
    foreach ($topAds as $a) {
        $s = $a['is_active'] ? '🟢' : '⚪️';
        $rows[] = [
            btn("{$s} 🔝 #{$a['id']}", 'chad_view:' . $a['id'], 'primary'),
            btn('🗑', 'chad_del:' . $a['id'], 'danger', emIcon('🗑')),
        ];
    }
    foreach ($schAds as $a) {
        $s = $a['is_active'] ? '🟢' : '⚪️';
        $rows[] = [
            btn("{$s} 🕐 #{$a['id']}", 'chad_view:' . $a['id'], 'primary'),
            btn('🗑', 'chad_del:' . $a['id'], 'danger', emIcon('🗑')),
        ];
    }
    $rows[] = [btn('➕ Top post reklama', 'chad_add:top_post:' . $pcId, 'success', emIcon('➕'))];
    $rows[] = [btn('➕ Vaqtli reklama', 'chad_add:scheduled:' . $pcId, 'success', emIcon('➕'))];
    $rows[] = [btn(($pc['is_active'] ? '⏸ Kanalni to\'xtatish' : '▶️ Kanalni yoqish'), 'chad_ch_toggle:' . $pcId, 'primary')];
    $rows[] = [btn('🗑 Kanalni o\'chirish', 'chad_ch_del:' . $pcId, 'danger', emIcon('🗑'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_chads_menu', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

function admChAdView($chatId, int $adId): void {
    $st = db()->prepare('SELECT ca.*, pc.title AS ch_title FROM channel_ads ca JOIN promo_channels pc ON pc.id = ca.promo_channel_id WHERE ca.id=?');
    $st->execute([$adId]);
    $a = $st->fetch(PDO::FETCH_ASSOC);
    if (!$a) { sendMessage($chatId, "❌ Topilmadi."); return; }

    $modeLabel = $a['ad_mode'] === 'top_post' ? '🔝 Top post' : '🕐 Vaqtli';
    $contentLabel = $a['content_mode'] === 'forward' ? '↪️ Forward' : '✉️ Oddiy';
    $text = "{$modeLabel} reklama #{$a['id']}\nKanal: " . h($a['ch_title']) . "\nTuri: {$contentLabel}\n";
    if ($a['ad_mode'] === 'top_post') {
        $text .= "So'nggi postdan keyin: {$a['delay_minutes']} daqiqa\nQayta yuborish (sokin bo'lsa): {$a['requeue_minutes']} daqiqa\n";
    } else {
        $times = json_decode($a['times_json'], true) ?: [];
        $text .= "Vaqtlar: " . (empty($times) ? '— yo\'q —' : implode(', ', $times)) . "\n";
    }
    $text .= "Eski postni o'chirish: " . ($a['auto_delete_prev'] ? 'YONIQ' : "O'CHIQ") . "\n";
    $text .= "Holati: " . ($a['is_active'] ? '🟢 faol' : '⚪️ to\'xtatilgan');

    $rows = [
        [btn(($a['is_active'] ? '⏸ To\'xtatish' : '▶️ Yoqish'), 'chad_toggle:' . $adId, 'primary')],
        [btn("♻️ Eski postni o'chirish: " . ($a['auto_delete_prev'] ? "O'CHIRISH" : 'YOQISH'), 'chad_delprev_toggle:' . $adId, 'primary')],
    ];
    if ($a['ad_mode'] === 'scheduled') $rows[] = [btn('🕐 Vaqtlarni tahrirlash', 'chad_edit_times:' . $adId, 'primary')];
    $rows[] = [btn('🗑 O\'chirish', 'chad_del:' . $adId, 'danger', emIcon('🗑'))];
    $rows[] = [btn('⬅️ Orqaga', 'chad_ch:' . $a['promo_channel_id'], null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

// Reklama kontentini (oddiy yoki forward) berilgan kanalga yuboradi, yangi message_id qaytaradi
function sendChannelAdContent(string $channelId, array $ca): ?int {
    if (($ca['content_mode'] ?? 'normal') === 'forward') {
        $r = tgApi('forwardMessage', ['chat_id' => $channelId, 'from_chat_id' => $ca['forward_chat_id'], 'message_id' => $ca['forward_message_id']]);
    } else {
        $kb = null;
        if (!empty($ca['button_text']) && !empty($ca['button_url'])) $kb = ikb([[ubtn($ca['button_text'], $ca['button_url'], 'primary')]]);
        $p = ['chat_id' => $channelId];
        if ($kb) $p['reply_markup'] = json_encode($kb);
        $text = $ca['text'] ?: '';
        if ($ca['content_type'] === 'photo') $r = tgApi('sendPhoto', array_merge($p, ['photo' => $ca['file_id']], captionPayload($text)));
        elseif ($ca['content_type'] === 'video') $r = tgApi('sendVideo', array_merge($p, ['video' => $ca['file_id']], captionPayload($text)));
        elseif ($ca['content_type'] === 'document') $r = tgApi('sendDocument', array_merge($p, ['document' => $ca['file_id']], captionPayload($text)));
        else $r = tgApi('sendMessage', array_merge($p, textPayload($text)));
    }
    return ($r && !empty($r['ok'])) ? (int) $r['result']['message_id'] : null;
}

function getChannelAdState(int $adId): array {
    $st = db()->prepare('SELECT * FROM channel_ad_state WHERE channel_ad_id=?');
    $st->execute([$adId]);
    $row = $st->fetch(PDO::FETCH_ASSOC);
    return $row ?: ['channel_ad_id' => $adId, 'last_ad_message_id' => null, 'last_ad_sent_at' => 0];
}

function upsertChannelAdState(int $adId, ?int $msgId, int $sentAt): void {
    $st = db()->prepare('INSERT INTO channel_ad_state (channel_ad_id, last_ad_message_id, last_ad_sent_at) VALUES (?,?,?) ON CONFLICT(channel_ad_id) DO UPDATE SET last_ad_message_id=excluded.last_ad_message_id, last_ad_sent_at=excluded.last_ad_sent_at');
    $st->execute([$adId, $msgId, $sentAt]);
}

// Har bir "top post" reklama uchun: oxirgi ODDIY (bizniki bo'lmagan) posdtan keyin
// belgilangan daqiqa o'tsa — yuboradi. Agar kanal sokin bo'lsa, requeue_minutes
// oralig'ida qayta-qayta yuborib turadi (top'da turishi uchun).
function processTopPostAd(array $pc, array $ca, int $now): void {
    $stp = db()->prepare('SELECT last_regular_post_at FROM promo_channel_state WHERE promo_channel_id=?');
    $stp->execute([$pc['id']]);
    $lastPost = (int) $stp->fetchColumn();
    $state = getChannelAdState((int) $ca['id']);
    $lastSent = (int) ($state['last_ad_sent_at'] ?? 0);
    $delay = max(1, (int) $ca['delay_minutes']) * 60;
    $requeue = max(1, (int) $ca['requeue_minutes']) * 60;

    $shouldSend = false;
    if ($lastPost > 0 && ($now - $lastPost) >= $delay && $lastSent < $lastPost) {
        $shouldSend = true; // yangi post kelib, kerakli vaqt o'tdi, hali reklama yuborilmagan
    } elseif ($lastSent > 0 && ($now - $lastSent) >= $requeue) {
        $shouldSend = true; // kanal sokin, top'da turishi uchun qayta yuborish vaqti keldi
    }
    if (!$shouldSend) return;

    if ($ca['auto_delete_prev'] && !empty($state['last_ad_message_id'])) {
        tgApi('deleteMessage', ['chat_id' => $pc['channel_id'], 'message_id' => $state['last_ad_message_id']]);
    }
    $newId = sendChannelAdContent($pc['channel_id'], $ca);
    upsertChannelAdState((int) $ca['id'], $newId, $now);
}

// Ma'lum vaqtlarda (masalan 08:00, 12:00) yuboriladigan reklama.
// Cron har necha daqiqada bir ishlasa ham, kun ichida har slot uchun FAQAT
// bir marta yuboriladi (channel_ad_sent_log orqali kuzatiladi).
function processScheduledAd(array $pc, array $ca, int $now): void {
    $times = json_decode($ca['times_json'], true);
    if (!is_array($times) || empty($times)) return;
    $today = date('Y-m-d', $now);
    foreach ($times as $t) {
        $t = trim($t);
        if (!preg_match('/^\d{1,2}:\d{2}$/', $t)) continue;
        $slotTs = strtotime("{$today} {$t}:00");
        if ($slotTs === false || $now < $slotTs) continue;

        $chk = db()->prepare('SELECT 1 FROM channel_ad_sent_log WHERE channel_ad_id=? AND slot_date=? AND slot_time=?');
        $chk->execute([$ca['id'], $today, $t]);
        if ($chk->fetchColumn()) continue; // shu kun+vaqt uchun allaqachon yuborilgan

        if ($ca['auto_delete_prev']) {
            $state = getChannelAdState((int) $ca['id']);
            if (!empty($state['last_ad_message_id'])) {
                tgApi('deleteMessage', ['chat_id' => $pc['channel_id'], 'message_id' => $state['last_ad_message_id']]);
            }
        }
        $newId = sendChannelAdContent($pc['channel_id'], $ca);
        upsertChannelAdState((int) $ca['id'], $newId, $now);
        db()->prepare('INSERT INTO channel_ad_sent_log (channel_ad_id, slot_date, slot_time) VALUES (?,?,?)')->execute([$ca['id'], $today, $t]);
    }
}

// Cron tomonidan chaqiriladi — barcha faol promo-kanal va ularning reklamalarini tekshiradi
function processChannelAds(): void {
    $now = time();
    $channels = db()->query('SELECT * FROM promo_channels WHERE is_active=1')->fetchAll(PDO::FETCH_ASSOC);
    foreach ($channels as $pc) {
        $st = db()->prepare('SELECT * FROM channel_ads WHERE promo_channel_id=? AND is_active=1');
        $st->execute([$pc['id']]);
        foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $ca) {
            try {
                if ($ca['ad_mode'] === 'top_post') processTopPostAd($pc, $ca, $now);
                else processScheduledAd($pc, $ca, $now);
            } catch (Throwable $e) {
                @file_put_contents(__DIR__ . '/error.log', date('Y-m-d H:i:s') . ' processChannelAds #' . $ca['id'] . ': ' . $e->getMessage() . "\n", FILE_APPEND);
            }
        }
    }
}

// channel_post webhook yangilanishi — kanalga yangi (oddiy) post kelganini kuzatadi.
// Bizning yuborgan reklamamiz "oddiy post" hisoblanmaydi (aks holda cheksiz aylanib qolardi).
function handleChannelPost(array $post): void {
    $chatId = (string) $post['chat']['id'];
    $msgId = (int) $post['message_id'];
    $st = db()->prepare('SELECT id FROM promo_channels WHERE channel_id=? AND is_active=1');
    $st->execute([$chatId]);
    $pcId = $st->fetchColumn();
    if (!$pcId) return;

    $st2 = db()->prepare('SELECT ca.id FROM channel_ads ca JOIN channel_ad_state s ON s.channel_ad_id = ca.id WHERE ca.promo_channel_id=? AND s.last_ad_message_id=?');
    $st2->execute([$pcId, $msgId]);
    if ($st2->fetchColumn()) return; // bu bizning reklama postimiz edi — hisobga olmaymiz

    $up = db()->prepare('INSERT INTO promo_channel_state (promo_channel_id, last_regular_post_at) VALUES (?,?) ON CONFLICT(promo_channel_id) DO UPDATE SET last_regular_post_at=excluded.last_regular_post_at');
    $up->execute([$pcId, time()]);
}

function admVipList($chatId): void {
    $st = db()->query('SELECT * FROM vip_plans ORDER BY id');
    $plans = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "💎 <b>VIP rejalar:</b>\n\n";
    $rows = [];
    if (empty($plans)) $text .= "— hozircha qo'shilmagan —\n";
    foreach ($plans as $p) {
        $text .= "• {$p['name']} — {$p['price']} so'm / {$p['duration_days']} kun\n";
        $rows[] = [btn("❌ O'chirish: " . $p['name'], 'adm_vip_del:' . $p['id'], 'danger', emIcon('❌'))];
    }
    $rows[] = [btn('➕ Reja qo\'shish', 'adm_vip_add', 'success', emIcon('➕'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

/* ---- 7.4b Premium (VIP) foydalanuvchilarni ID orqali qo'lda boshqarish ---- */

function admPaymentMenu($chatId): void {
    $humo = getSetting('card_humo_number', '');
    $uzcard = getSetting('card_uzcard_number', '');
    $adminUsername = getSetting('admin_username', '');
    $text = "💳 <b>To'lov sozlamalari</b>\n\n";
    $text .= "Humo: " . ($humo ? "<code>" . h($humo) . "</code>" : "— sozlanmagan —") . "\n";
    $text .= "Uzcard: " . ($uzcard ? "<code>" . h($uzcard) . "</code>" : "— sozlanmagan —") . "\n";
    $text .= "Admin username: " . ($adminUsername ? "@" . h($adminUsername) : "— sozlanmagan —") . "\n\n";
    $text .= "❗️ Foydalanuvchiga har safar bazaviy narxga tasodifiy 1-99 so'm qo'shilib, noyob summa ko'rsatiladi — bu to'lovlarni farqlash uchun kerak.";
    sendMessage($chatId, $text, ikb([
        [btn('💳 Humo kartani sozlash', 'adm_pay_humo', 'primary', emIcon('💳'))],
        [btn('💳 Uzcard kartani sozlash', 'adm_pay_uzcard', 'primary', emIcon('💳'))],
        [btn('👤 Admin username', 'adm_pay_username', 'primary', emIcon('👤'))],
        [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))],
    ]));
}

function admPremiumMenu($chatId): void {
    $st = db()->query("SELECT telegram_id, vip_until FROM users WHERE is_vip=1 AND vip_until > " . time() . " ORDER BY vip_until DESC LIMIT 30");
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "🌟 <b>Premium (VIP) foydalanuvchilar</b>\n\n";
    if (empty($rows)) {
        $text .= "— hozircha faol VIP foydalanuvchi yo'q —\n";
    } else {
        foreach ($rows as $r) {
            $left = (int) $r['vip_until'] - time();
            $days = max(0, (int) floor($left / 86400));
            $text .= "• <code>{$r['telegram_id']}</code> — {$days} kun qoldi\n";
        }
    }
    $kb = ikb([
        [btn('➕ ID orqali qo\'shish', 'adm_prem_add', 'success', emIcon('➕')), btn('➖ ID orqali olib tashlash', 'adm_prem_del', 'danger', emIcon('➖'))],
        [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))],
    ]);
    sendMessage($chatId, $text, $kb);
}

/* ---- 7.5 Adminlar ---- */

function admAdminsList($chatId): void {
    $st = db()->query('SELECT * FROM admins ORDER BY telegram_id');
    $admins = $st->fetchAll(PDO::FETCH_ASSOC);
    $text = "🛠 <b>Adminlar:</b>\n\n• " . SUPER_ADMIN_ID . " (super-admin)\n";
    $rows = [];
    foreach ($admins as $a) {
        $text .= "• {$a['telegram_id']} ({$a['role']})\n";
        $rows[] = [btn("❌ O'chirish: {$a['telegram_id']}", 'adm_adm_del:' . $a['telegram_id'], 'danger', emIcon('❌'))];
    }
    $rows[] = [btn('➕ Admin qo\'shish', 'adm_adm_add', 'success', emIcon('➕'))];
    $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
    sendMessage($chatId, $text, ikb($rows));
}

/* ===================== 8) YANGILANISH (UPDATE) QAYTA ISHLASH ===================== */

function processTextState(array $admin, array $msg): bool {
    $adminId = (int) $admin['telegram_id'];
    $chatId = $msg['chat']['id'];
    $state = $admin['state'];
    $text = trim($msg['text'] ?? '');
    $data = getStateData($admin);

    switch ($state) {
        case 'adm_ch_edit_wait_id':
            if ($text === '') { sendMessage($chatId, "❌ Bo'sh bo'lishi mumkin emas."); return true; }
            $key = $data['which'] === 'storage' ? 'storage_channel_id' : 'codes_channel_id';
            setSetting($key, $text);
            clearState($adminId);
            sendMessage($chatId, "✅ Kanal yangilandi: <code>" . h($text) . "</code>");
            admChannelsList($chatId);
            return true;
        case 'adm_ch_wait_id':
            $data['channel_id'] = $text;
            if ($data['type'] === 'public') {
                setState($adminId, 'adm_ch_wait_title', $data);
                sendMessage($chatId, "Kanal nomini (ko'rinadigan nom) yuboring.");
            } else {
                setState($adminId, 'adm_ch_wait_link', $data);
                sendMessage($chatId, "Endi shu kanalning taklif (invite) linkini yuboring.\nMasalan: https://t.me/+AbCdEfGhIjKl");
            }
            return true;
        case 'adm_ch_wait_link':
            $data['invite_link'] = $text;
            setState($adminId, 'adm_ch_wait_title', $data);
            $label = $data['type'] === 'optional' ? "Tugma nomini yuboring (masalan: Bizning sayt)." : "Kanal nomini (ko'rinadigan nom) yuboring.";
            sendMessage($chatId, $label);
            return true;
        case 'adm_ch_wait_title':
            $data['title'] = $text;
            $ins = db()->prepare('INSERT INTO channels (channel_id, title, type, invite_link, is_active, created_at) VALUES (?,?,?,?,1,?)');
            $ins->execute([$data['channel_id'] ?? '', $data['title'], $data['type'], $data['invite_link'] ?? null, time()]);
            clearState($adminId);
            sendMessage($chatId, "✅ Qo'shildi.");
            admChannelsList($chatId);
            return true;

        case 'adm_vip_wait_name':
            $data['name'] = $text;
            setState($adminId, 'adm_vip_wait_price', $data);
            sendMessage($chatId, "Narxini kiriting (masalan: 25000).");
            return true;
        case 'adm_vip_wait_price':
            $data['price'] = $text;
            setState($adminId, 'adm_vip_wait_days', $data);
            sendMessage($chatId, "Muddatini kunlarda kiriting (masalan: 30).");
            return true;
        case 'adm_vip_wait_days':
            if (!ctype_digit($text)) { sendMessage($chatId, 'Faqat raqam kiriting.'); return true; }
            $data['days'] = (int) $text;
            setState($adminId, 'adm_vip_wait_desc', $data);
            sendMessage($chatId, "Reja uchun qisqa tavsif yuboring.");
            return true;
        case 'adm_vip_wait_desc':
            $ins = db()->prepare('INSERT INTO vip_plans (name, price, duration_days, description, is_active) VALUES (?,?,?,?,1)');
            $ins->execute([$data['name'], $data['price'], $data['days'], $text]);
            clearState($adminId);
            sendMessage($chatId, "✅ VIP reja qo'shildi.");
            admVipList($chatId);
            return true;

        case 'adm_prem_add_wait_id':
            if (!ctype_digit($text)) { sendMessage($chatId, "Faqat Telegram ID (raqam) kiriting."); return true; }
            $data['target_id'] = (int) $text;
            setState($adminId, 'adm_prem_add_wait_days', $data);
            sendMessage($chatId, "Necha kunlik premium beriladi? (raqam kiriting, masalan 30)");
            return true;
        case 'adm_prem_add_wait_days':
            if (!ctype_digit($text)) { sendMessage($chatId, "Faqat raqam kiriting."); return true; }
            $days = (int) $text;
            $targetId = (int) $data['target_id'];
            $exists = getUser($targetId);
            if (!$exists) {
                $ins = db()->prepare('INSERT INTO users (telegram_id, joined_at, last_active_at, is_vip, vip_until) VALUES (?,?,?,1,?)');
                $ins->execute([$targetId, time(), time(), time() + $days * 86400]);
            } else {
                $upd = db()->prepare('UPDATE users SET is_vip=1, vip_until=? WHERE telegram_id=?');
                $upd->execute([time() + $days * 86400, $targetId]);
            }
            clearState($adminId);
            sendMessage($chatId, "✅ Foydalanuvchi <code>{$targetId}</code> {$days} kunlik premium qilindi.");
            tgApi('sendMessage', ['chat_id' => $targetId, 'text' => "🎉 Sizga admin tomonidan {$days} kunlik VIP obuna berildi!", 'parse_mode' => 'HTML']);
            ensureBottomKeyboard($targetId, $targetId);
            admPremiumMenu($chatId);
            return true;
        case 'adm_prem_del_wait_id':
            if (!ctype_digit($text)) { sendMessage($chatId, "Faqat Telegram ID (raqam) kiriting."); return true; }
            $targetId = (int) $text;
            $upd = db()->prepare('UPDATE users SET is_vip=0, vip_until=0 WHERE telegram_id=?');
            $upd->execute([$targetId]);
            clearState($adminId);
            sendMessage($chatId, "✅ Foydalanuvchi <code>{$targetId}</code>ning premiumi bekor qilindi.");
            $vipRemovedKb = ikb([[btn('🧑‍💻 Adminga murojaat', 'support_start', 'primary', emIcon('🧑‍💻'))]]);
            tgApi('sendMessage', array_merge(['chat_id' => $targetId, 'reply_markup' => json_encode($vipRemovedKb)], textPayload("❗️ Sizning 💎 VIP obunangiz admin tomonidan bekor qilindi.\n\nSavolingiz bo'lsa, pastdagi tugma orqali adminga murojaat qiling.")));
            admPremiumMenu($chatId);
            return true;

        case 'adm_pay_humo_wait_num':
            if ($text === '/skip') { setSetting('card_humo_number', ''); clearState($adminId); sendMessage($chatId, "✅ Humo karta o'chirildi."); admPaymentMenu($chatId); return true; }
            setSetting('card_humo_number', $text);
            setState($adminId, 'adm_pay_humo_wait_owner', []);
            sendMessage($chatId, "Humo karta egasining Ism Familiyasini yuboring.");
            return true;
        case 'adm_pay_humo_wait_owner':
            setSetting('card_humo_owner', $text);
            clearState($adminId);
            sendMessage($chatId, "✅ Humo karta ma'lumotlari saqlandi.");
            admPaymentMenu($chatId);
            return true;
        case 'adm_pay_uzcard_wait_num':
            if ($text === '/skip') { setSetting('card_uzcard_number', ''); clearState($adminId); sendMessage($chatId, "✅ Uzcard karta o'chirildi."); admPaymentMenu($chatId); return true; }
            setSetting('card_uzcard_number', $text);
            setState($adminId, 'adm_pay_uzcard_wait_owner', []);
            sendMessage($chatId, "Uzcard karta egasining Ism Familiyasini yuboring.");
            return true;
        case 'adm_pay_uzcard_wait_owner':
            setSetting('card_uzcard_owner', $text);
            clearState($adminId);
            sendMessage($chatId, "✅ Uzcard karta ma'lumotlari saqlandi.");
            admPaymentMenu($chatId);
            return true;
        case 'adm_pay_username_wait':
            setSetting('admin_username', ltrim($text, '@'));
            clearState($adminId);
            sendMessage($chatId, "✅ Admin username saqlandi.");
            admPaymentMenu($chatId);
            return true;

        case 'adm_limit_wait':
            if (!ctype_digit($text)) { sendMessage($chatId, 'Faqat raqam kiriting.'); return true; }
            setSetting('daily_limit', $text);
            clearState($adminId);
            sendMessage($chatId, "✅ Kunlik limit {$text} taga o'rnatildi.");
            return true;

        case 'adm_emoji_wait_id':
            $map = emojiMap();
            $emoji = $data['emoji'];
            if ($text === '/skip') {
                unset($map[$emoji]);
            } else {
                if (!ctype_digit($text)) { sendMessage($chatId, "❌ custom_emoji_id faqat raqamlardan iborat bo'lishi kerak."); return true; }
                $map[$emoji] = $text;
            }
            setSetting('emoji_map_json', json_encode($map, JSON_UNESCAPED_UNICODE));
            clearState($adminId);
            sendMessage($chatId, "✅ {$emoji} uchun premium emoji yangilandi.");
            admEmojiPackMenu($chatId);
            return true;

        case 'adm_emoji_add_wait_emoji':
            $newEmoji = mb_substr($text, 0, 8, 'UTF-8');
            if ($newEmoji === '') { sendMessage($chatId, "❌ Bo'sh bo'lishi mumkin emas. Emoji yuboring."); return true; }
            $data['new_emoji'] = $newEmoji;
            setState($adminId, 'adm_emoji_add_wait_id', $data);
            sendMessage($chatId, "🔢 Endi \"{$newEmoji}\" uchun custom_emoji_id raqamini yuboring.\n\ncustom_emoji_id qanday olinishi haqida faylning yuqorisidagi izohga qarang.");
            return true;

        case 'adm_emoji_add_wait_id':
            if (!ctype_digit($text)) { sendMessage($chatId, "❌ custom_emoji_id faqat raqamlardan iborat bo'lishi kerak."); return true; }
            $map = emojiMap();
            $map[$data['new_emoji']] = $text;
            setSetting('emoji_map_json', json_encode($map, JSON_UNESCAPED_UNICODE));
            clearState($adminId);
            sendMessage($chatId, "✅ Yangi emoji ({$data['new_emoji']}) ro'yxatga qo'shildi.");
            admEmojiPackMenu($chatId);
            return true;

        case 'adm_adm_wait_id':
            if (!ctype_digit($text)) { sendMessage($chatId, 'Faqat Telegram ID (raqam) kiriting.'); return true; }
            $data['new_admin_id'] = (int) $text;
            setState($adminId, 'adm_adm_wait_role', $data);
            sendMessage($chatId, "Rolini tanlang:", ikb([
                [btn('Admin', 'admrole:admin', 'primary', emIcon('🛠')), btn('Moderator', 'admrole:moderator', 'success', emIcon('🛠'))],
            ]));
            return true;

        case 'admov_wait_code':
            $m = findMovieByCode($text);
            if (!$m) { sendMessage($chatId, "❌ Bunday kodli kino topilmadi. Qaytadan kod yuboring."); return true; }
            setState($adminId, 'admov_menu', ['movie_id' => $m['id']]);
            $isSeries = ($m['type'] ?? 'movie') === 'series';
            $accLabel = ($m['access'] ?? 'all') === 'vip' ? '🌟 Faqat VIP uchun' : '👥 Barcha uchun';
            $typeLine = $isSeries ? ("📺 <b>Serial</b> — " . count(movieEpisodes((int) $m['id'])) . " ta qism\n") : "🎬 <b>Kino</b>\n";
            $mtxt = $typeLine . h($m['title']) . "\nKod: <code>" . h($m['code']) . "</code>\nKimlar uchun: {$accLabel}\nKo'rilgan: {$m['views_count']} marta\n\n" . h($m['description']);
            $rows = [
                [btn("✏️ Nomini o'zgartirish", 'admov_title:' . $m['id'], 'primary', emIcon('✏️')), btn("🔢 Kodini o'zgartirish", 'admov_code:' . $m['id'], 'primary', emIcon('🔢'))],
                [btn("📄 Tavsifini o'zgartirish", 'admov_desc:' . $m['id'], 'primary', emIcon('📄'))],
                [btn("🔁 Kimlar uchun: almashtirish", 'admov_acc:' . $m['id'], 'primary', vipIcon())],
            ];
            if ($isSeries) $rows[] = [btn("➕ Yana qism qo'shish", 'admov_addep:' . $m['id'], 'success', emIcon('➕'))];
            $rows[] = [btn("🗑 O'chirish", 'admov_del:' . $m['id'], 'danger', emIcon('🗑'))];
            $rows[] = [btn('⬅️ Orqaga', 'adm_main', null, emIcon('⬅️'))];
            sendMessage($chatId, $mtxt, ikb($rows));
            return true;
        case 'admov_wait_newtitle':
            $u = db()->prepare('UPDATE movies SET title=? WHERE id=?');
            $u->execute([$text, $data['movie_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Kino nomi yangilandi.");
            return true;
        case 'admov_wait_newcode':
            $exists = findMovieByCode($text);
            if ($exists && (int) $exists['id'] !== (int) $data['movie_id']) { sendMessage($chatId, "❌ Bu kod band. Boshqa kod yuboring."); return true; }
            $u = db()->prepare('UPDATE movies SET code=? WHERE id=?');
            $u->execute([$text, $data['movie_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Kino kodi yangilandi.");
            return true;
        case 'admov_wait_newdesc':
            $u = db()->prepare('UPDATE movies SET description=? WHERE id=?');
            $u->execute([$text, $data['movie_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Kino tavsifi yangilandi.");
            return true;

        case 'adm_startmsg_wait_text':
            if ($text !== '/skip') setSetting('start_text', $text);
            setState($adminId, 'adm_startmsg_wait_photo', []);
            sendMessage($chatId, "Endi shu xabar uchun rasm yuboring (ixtiyoriy).\nKerak bo'lmasa /skip deb yozing.");
            return true;
        case 'adm_codemsg_wait_text':
            if ($text !== '/skip') setSetting('code_prompt_text', $text);
            setState($adminId, 'adm_codemsg_wait_photo', []);
            sendMessage($chatId, "Endi shu xabar uchun rasm yuboring (ixtiyoriy).\nKerak bo'lmasa /skip deb yozing.");
            return true;
        case 'adm_expmsg_wait_text':
            if ($text !== '/skip') setSetting('expired_text', $text);
            setState($adminId, 'adm_expmsg_wait_photo', []);
            sendMessage($chatId, "Endi shu xabar uchun rasm yuboring (ixtiyoriy).\nKerak bo'lmasa /skip deb yozing.");
            return true;

        case 'bc_wait_button_text':
            if (mb_strtolower($text) === "yo'q" || mb_strtolower($text) === 'yoq') {
                $data['button'] = null;
                $data = finalizeBroadcastPreview($adminId, $chatId, $data);
            } else {
                $data['button_text'] = $text;
                setState($adminId, 'bc_wait_button_url', $data);
                sendMessage($chatId, "Tugma uchun havolani (URL) yuboring.");
            }
            return true;
        case 'bc_wait_button_url':
            $data['button'] = ['text' => $data['button_text'], 'url' => $text];
            finalizeBroadcastPreview($adminId, $chatId, $data);
            return true;

        case 'ad_wait_button_text':
            if ($text === '/skip') {
                setState($adminId, 'ad_wait_duration', $data);
                sendMessage($chatId, "Reklama necha soniya davom etsin? (masalan: 10)\n\n❗️ Ba'zi hostinglarda 20-30 soniyadan uzoq reklama serverning vaqt chegarasiga urilib qolishi mumkin — 5-15 soniya tavsiya etiladi.");
            } else {
                $data['button_text'] = $text;
                setState($adminId, 'ad_wait_button_url', $data);
                sendMessage($chatId, "Tugma uchun havolani (URL) yuboring.");
            }
            return true;
        case 'ad_wait_button_url':
            $data['button_url'] = $text;
            setState($adminId, 'ad_wait_duration', $data);
            sendMessage($chatId, "Reklama necha soniya davom etsin? (masalan: 10)");
            return true;
        case 'ad_wait_duration':
            if (!ctype_digit($text) || (int) $text < 1) { sendMessage($chatId, "Faqat musbat raqam kiriting."); return true; }
            $data['duration_seconds'] = (int) $text;
            if (($data['purpose'] ?? 'movie') === 'limit_bypass') {
                finalizeAd($adminId, $chatId, $data, 'bypass');
                return true;
            }
            setState($adminId, 'ad_wait_codes', $data);
            sendMessage($chatId, "Bu reklama qaysi kino kodlari oldidan chiqsin?\n\nBitta bo'lsa: <code>1</code>\nBir nechta bo'lsa: <code>4|6|7|8</code>\n\nYoki pastdagi tugmani bosing:", ikb([[btn('🌐 Hammasi', 'ad_codes_all', 'primary', emIcon('🌐'))]]));
            return true;
        case 'ad_wait_codes':
            $data['duration_seconds'] = $data['duration_seconds'] ?? 10;
            finalizeAd($adminId, $chatId, $data, $text);
            return true;

        case 'ad_edit_wait_duration':
            if (!ctype_digit($text) || (int) $text < 1) { sendMessage($chatId, "Faqat musbat raqam kiriting."); return true; }
            db()->prepare('UPDATE ads SET duration_seconds=? WHERE id=?')->execute([(int) $text, $data['ad_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Vaqti yangilandi.");
            return true;
        case 'ad_edit_wait_codes':
            db()->prepare('UPDATE ads SET target_codes=? WHERE id=?')->execute([trim($text) !== '' ? trim($text) : 'all', $data['ad_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Kodlari yangilandi.");
            return true;
        case 'ad_edit_wait_text':
            db()->prepare('UPDATE ads SET text=? WHERE id=?')->execute([$text, $data['ad_id']]);
            clearState($adminId);
            sendMessage($chatId, "✅ Matni yangilandi.");
            return true;

        case 'chad_ch_wait_id':
            $data['channel_id'] = $text;
            setState($adminId, 'chad_ch_wait_title', $data);
            sendMessage($chatId, "Kanal nomini (o'zingiz uchun, ko'rinadigan nom) yuboring.");
            return true;
        case 'chad_ch_wait_title':
            $ins = db()->prepare('INSERT INTO promo_channels (channel_id, title, is_active, created_at) VALUES (?,?,1,?)');
            $ins->execute([$data['channel_id'], $text, time()]);
            clearState($adminId);
            sendMessage($chatId, "✅ Kanal qo'shildi.");
            admChAdsMenu($chatId);
            return true;

        case 'chad_wait_button_text':
            if ($text === '/skip') {
                $data['button_text'] = null; $data['button_url'] = null;
                if ($data['ad_mode'] === 'top_post') {
                    setState($adminId, 'chad_wait_delay', $data);
                    sendMessage($chatId, "So'nggi kanal postidan necha daqiqa o'tgach reklama yuborilsin? (masalan: 30)");
                } else {
                    setState($adminId, 'chad_wait_times', $data);
                    sendMessage($chatId, "Vaqtlarni yuboring (24 soatlik formatda, vergul bilan ajratib):\n\nMasalan: <code>08:00, 12:00, 18:30, 22:00</code>");
                }
            } else {
                $data['button_text'] = $text;
                setState($adminId, 'chad_wait_button_url', $data);
                sendMessage($chatId, "Tugma uchun havolani (URL) yuboring.");
            }
            return true;
        case 'chad_wait_button_url':
            $data['button_url'] = $text;
            if ($data['ad_mode'] === 'top_post') {
                setState($adminId, 'chad_wait_delay', $data);
                sendMessage($chatId, "So'nggi kanal postidan necha daqiqa o'tgach reklama yuborilsin? (masalan: 30)");
            } else {
                setState($adminId, 'chad_wait_times', $data);
                sendMessage($chatId, "Vaqtlarni yuboring (24 soatlik formatda, vergul bilan ajratib):\n\nMasalan: <code>08:00, 12:00, 18:30, 22:00</code>");
            }
            return true;
        case 'chad_wait_delay':
            if (!ctype_digit($text) || (int) $text < 1) { sendMessage($chatId, "Faqat musbat raqam kiriting."); return true; }
            $data['delay_minutes'] = (int) $text;
            setState($adminId, 'chad_wait_requeue', $data);
            sendMessage($chatId, "Agar kanal sokin bo'lsa (yangi post kelmasa), reklama necha daqiqada bir qayta yuborilsin? (masalan: 60)");
            return true;
        case 'chad_wait_requeue':
            if (!ctype_digit($text) || (int) $text < 1) { sendMessage($chatId, "Faqat musbat raqam kiriting."); return true; }
            $data['requeue_minutes'] = (int) $text;
            finalizeChannelAd($adminId, $chatId, $data);
            return true;
        case 'chad_wait_times':
            $parts = array_map('trim', explode(',', $text));
            $times = [];
            foreach ($parts as $p) { if (preg_match('/^\d{1,2}:\d{2}$/', $p)) $times[] = $p; }
            if (empty($times)) { sendMessage($chatId, "❌ Hech qanday to'g'ri vaqt topilmadi. Masalan: 08:00, 12:00"); return true; }
            if (isset($data['ad_id'])) {
                // mavjud reklamani tahrirlash
                db()->prepare('UPDATE channel_ads SET times_json=? WHERE id=?')->execute([json_encode($times), $data['ad_id']]);
                clearState($adminId);
                sendMessage($chatId, "✅ Vaqtlar yangilandi.");
                admChAdView($chatId, (int) $data['ad_id']);
                return true;
            }
            $data['times'] = $times;
            finalizeChannelAd($adminId, $chatId, $data);
            return true;

        case 'up_wait_code':
        case 'up_wait_title':
        case 'up_wait_desc':
            handleUploadFlow($admin, $msg);
            return true;
    }
    return false;
}

function finalizeBroadcastPreview(int $adminId, $chatId, array $data): array {
    setState($adminId, 'bc_wait_confirm', $data);
    $kb = null;
    if (!empty($data['button'])) $kb = ikb([[ubtn($data['button']['text'], $data['button']['url'])]]);
    sendBroadcastPreview($chatId, $data, $kb);
    sendMessage($chatId, "Yuqoridagi xabar barcha foydalanuvchilarga yuboriladi. Tasdiqlaysizmi?", ikb([
        [btn('✅ Yuborish', 'bc_confirm', 'success', emIcon('✅')), btn('❌ Bekor qilish', 'bc_cancel', 'danger', emIcon('❌'))],
    ]));
    return $data;
}

function sendBroadcastPreview($chatId, array $data, ?array $kb): void {
    $p = ['chat_id' => $chatId];
    if ($kb) $p['reply_markup'] = json_encode($kb);
    $txt = $data['text'] ?? '';
    if ($data['type'] === 'text') {
        tgApi('sendMessage', array_merge($p, textPayload($txt)));
    } elseif ($data['type'] === 'photo') {
        $p['photo'] = $data['file_id'];
        tgApi('sendPhoto', array_merge($p, captionPayload($txt)));
    } elseif ($data['type'] === 'video') {
        $p['video'] = $data['file_id'];
        tgApi('sendVideo', array_merge($p, captionPayload($txt)));
    } elseif ($data['type'] === 'document') {
        $p['document'] = $data['file_id'];
        tgApi('sendDocument', array_merge($p, captionPayload($txt)));
    }
}

function runBroadcast(int $adminId, $chatId, array $data): void {
    $kb = null;
    if (!empty($data['button'])) $kb = ikb([[ubtn($data['button']['text'], $data['button']['url'])]]);

    $st = db()->query('SELECT telegram_id FROM users WHERE is_blocked=0');
    $ids = $st->fetchAll(PDO::FETCH_COLUMN);

    $sent = 0; $failed = 0;
    foreach ($ids as $uid) {
        $ok = false;
        $p = ['chat_id' => $uid];
        if ($kb) $p['reply_markup'] = json_encode($kb);
        $txt = $data['text'] ?? '';
        if ($data['type'] === 'text') { $r = tgApi('sendMessage', array_merge($p, textPayload($txt))); }
        elseif ($data['type'] === 'photo') { $p['photo'] = $data['file_id']; $r = tgApi('sendPhoto', array_merge($p, captionPayload($txt))); }
        elseif ($data['type'] === 'video') { $p['video'] = $data['file_id']; $r = tgApi('sendVideo', array_merge($p, captionPayload($txt))); }
        elseif ($data['type'] === 'document') { $p['document'] = $data['file_id']; $r = tgApi('sendDocument', array_merge($p, captionPayload($txt))); }
        else { $r = null; }

        if ($r && !empty($r['ok'])) { $sent++; $ok = true; }
        else {
            $failed++;
            if ($r && isset($r['error_code']) && (int) $r['error_code'] === 403) {
                $u = db()->prepare('UPDATE users SET is_blocked=1 WHERE telegram_id=?');
                $u->execute([$uid]);
            }
        }
        usleep(50000); // flood-limitdan saqlanish uchun
    }

    clearState($adminId);
    sendMessage($chatId, "📨 Xabarnoma yuborildi.\n✅ Yuborildi: {$sent}\n❌ Xato: {$failed}");
}

function runBroadcastForward(int $adminId, $chatId, array $data): void {
    $st = db()->query('SELECT telegram_id FROM users WHERE is_blocked=0');
    $ids = $st->fetchAll(PDO::FETCH_COLUMN);

    $sent = 0; $failed = 0;
    foreach ($ids as $uid) {
        $r = tgApi('forwardMessage', [
            'chat_id' => $uid,
            'from_chat_id' => $data['forward_chat_id'],
            'message_id' => $data['forward_message_id'],
        ]);
        if ($r && !empty($r['ok'])) { $sent++; }
        else {
            $failed++;
            if ($r && isset($r['error_code']) && (int) $r['error_code'] === 403) {
                $u = db()->prepare('UPDATE users SET is_blocked=1 WHERE telegram_id=?');
                $u->execute([$uid]);
            }
        }
        usleep(50000);
    }

    clearState($adminId);
    sendMessage($chatId, "📨 Xabarnoma forward qilindi.\n✅ Yuborildi: {$sent}\n❌ Xato: {$failed}");
}

/* ------------------------- Callback query ishlovchisi ------------------------- */

function handleCallback(array $cb): void {
    $data = $cb['data'];
    $from = $cb['from'];
    $userId = (int) $from['id'];
    $chatId = $cb['message']['chat']['id'];
    $messageId = $cb['message']['message_id'];

    upsertUser($userId, $from['username'] ?? null, trim(($from['first_name'] ?? '') . ' ' . ($from['last_name'] ?? '')));

    // save_movie alohida ishlov beriladi, chunki unga alert (ko'rsatkichli xabar)
    // bilan javob berish kerak — shuning uchun pastdagi "bo'sh" javobdan oldin turadi.
    if (str_starts_with($data, 'save_movie:')) {
        $movieId = (int) explode(':', $data)[1];
        $st = db()->prepare('SELECT 1 FROM saved_movies WHERE user_id=? AND movie_id=?');
        $st->execute([$userId, $movieId]);
        if (!$st->fetchColumn()) {
            $ins = db()->prepare('INSERT INTO saved_movies (user_id, movie_id, created_at) VALUES (?,?,?)');
            $ins->execute([$userId, $movieId, time()]);
        }
        answerCb($cb['id'], '💾 Saqlandi! "Saqlanganlarim" bo\'limidan topasiz.', true);
        return;
    }

    answerCb($cb['id']);

    if ($data === 'menu_normal') { handleMenuNormal($userId, $chatId); return; }
    if ($data === 'menu_vip') { handleMenuVip($chatId); return; }

    if ($data === 'chk_sub') {
        $user = getUser($userId);
        $st = $user['state'] ?? '';
        $sd = getStateData($user);
        $missing = missingChannels($userId);
        if (!empty($missing)) {
            sendSubscribePrompt($chatId, $missing, "❗️ Siz hali barcha kanallarga obuna bo'lmadingiz. Qaytadan tekshiring:");
            return;
        }
        if (!empty($sd['code'])) {
            attemptDeliverMovie($userId, $chatId, $sd['code']);
        } else {
            clearState($userId);
            sendCodePrompt($chatId, $userId);
        }
        return;
    }

    if ($data === 'top10') { showTop10($chatId, $userId); return; }

    if ($data === 'my_saved') { showMySaved($chatId, $userId); return; }

    if (str_starts_with($data, 'get_saved:')) {
        $code = substr($data, strlen('get_saved:'));
        attemptDeliverMovie($userId, $chatId, $code);
        return;
    }

    if (str_starts_with($data, 'watch_ad_bypass:')) {
        $code = substr($data, strlen('watch_ad_bypass:'));
        $ad = findLimitBypassAd();
        if (!$ad) { sendMessage($chatId, "❌ Hozircha reklama mavjud emas."); return; }
        showAdWithCountdown($chatId, $ad);
        grantBonusView($userId);
        sendMessage($chatId, "✅ Rahmat! Endi yana 1 ta kino ko'rishingiz mumkin — kodni yuboring.");
        return;
    }

    if ($data === 'my_status') {
        if (!ensureSubscribedForBasicFeature($userId, $chatId)) return;
        showMyStatus($chatId, $userId);
        return;
    }

    if ($data === 'support_start') {
        if (!ensureSubscribedForBasicFeature($userId, $chatId)) return;
        setState($userId, 'support_wait_msg', []);
        sendMessage($chatId, "✍️ Xabaringizni yozing — men adminga yuboraman.");
        return;
    }

    if (str_starts_with($data, 'vip_plan:')) {
        $planId = (int) explode(':', $data)[1];
        startVipPayment($userId, $chatId, $planId);
        return;
    }

    if (str_starts_with($data, 'pay_method:')) {
        [, $method, $planId] = explode(':', $data);
        showPaymentAmount($userId, $chatId, (int) $planId, $method);
        return;
    }

    if (str_starts_with($data, 'paid_confirm:')) {
        $payId = (int) explode(':', $data)[1];
        $st = db()->prepare('SELECT * FROM vip_payments WHERE id=?');
        $st->execute([$payId]);
        $pay = $st->fetch(PDO::FETCH_ASSOC);
        if (!$pay || (int) $pay['user_id'] !== $userId || $pay['status'] !== 'awaiting_payment') {
            sendMessage($chatId, "❌ Bu to'lov topilmadi.");
            return;
        }
        if ((int) $pay['reserved_until'] < time()) {
            $adminUsername = getSetting('admin_username', '');
            $extra = $adminUsername ? " (@" . h($adminUsername) . ")" : '';
            sendMessage($chatId, "⏳ To'lov vaqti (10 daqiqa) tugadi va bekor qilindi.\n\nIltimos, agar to'lov qilgan bo'lsangiz-u vaqt tugagan bo'lsa, adminga murojaat qiling{$extra}, aks holda qaytadan urinib ko'ring.", ikb([[btn('💎 VIP', 'menu_vip', 'primary', vipIcon())]]));
            $upd = db()->prepare("UPDATE vip_payments SET status='expired' WHERE id=?");
            $upd->execute([$payId]);
            return;
        }
        setState($userId, 'vip_wait_receipt', ['payment_id' => $payId]);
        sendMessage($chatId, "📸 Endi to'lov chekini (skrinshot yoki fayl) yuboring.");
        return;
    }

    if (str_starts_with($data, 'vip_approve:') || str_starts_with($data, 'vip_reject:')) {
        if (!isAdmin($userId)) {
            sendMessage($chatId, "⛔️ Sizda bu amalni bajarish uchun ruxsat yo'q.\n\nSizning Telegram ID'ingiz: <code>{$userId}</code>\n\nFayl boshidagi SUPER_ADMIN_ID shu raqamga teng ekanini tekshiring (hozir u to'g'ri sozlanmagan bo'lishi mumkin).");
            return;
        }
        [$act, $payId] = explode(':', $data);
        $payId = (int) $payId;
        try {
            $st = db()->prepare('SELECT * FROM vip_payments WHERE id=?');
            $st->execute([$payId]);
            $pay = $st->fetch(PDO::FETCH_ASSOC);
            if (!$pay || $pay['status'] !== 'pending') { sendMessage($chatId, "Bu so'rov allaqachon ko'rib chiqilgan."); return; }

            if ($act === 'vip_approve') {
                $stp = db()->prepare('SELECT * FROM vip_plans WHERE id=?');
                $stp->execute([$pay['plan_id']]);
                $plan = $stp->fetch(PDO::FETCH_ASSOC);
                $days = $plan ? (int) $plan['duration_days'] : 30;

                $u = db()->prepare('UPDATE users SET is_vip=1, vip_until=?, vip_plan_id=? WHERE telegram_id=?');
                $u->execute([time() + $days * 86400, $pay['plan_id'], $pay['user_id']]);

                $upd = db()->prepare("UPDATE vip_payments SET status='approved', admin_id=?, resolved_at=? WHERE id=?");
                $upd->execute([$userId, time(), $payId]);

                sendMessage($pay['user_id'], "🎉 Tabriklaymiz! Sizning VIP obunangiz tasdiqlandi va faollashtirildi ({$days} kun).");
                ensureBottomKeyboard($pay['user_id'], (int) $pay['user_id']);
                tgApi('deleteMessage', ['chat_id' => $chatId, 'message_id' => $messageId]);
                sendMessage($chatId, "✅ <code>{$pay['user_id']}</code> ID egasi <b>{$days} kunlik VIP</b>ga ega bo'ldi!");
            } else {
                $upd = db()->prepare("UPDATE vip_payments SET status='rejected', admin_id=?, resolved_at=? WHERE id=?");
                $upd->execute([$userId, time(), $payId]);
                sendMessage($pay['user_id'], "❌ Afsuski, sizning to'lov so'rovingiz rad etildi. Qayta urinib ko'rishingiz mumkin.");
                tgApi('deleteMessage', ['chat_id' => $chatId, 'message_id' => $messageId]);
                sendMessage($chatId, "❌ <code>{$pay['user_id']}</code> ID egasining to'lov so'rovi rad etildi.");
            }
        } catch (Throwable $e) {
            sendMessage($chatId, "❌ Xatolik yuz berdi: " . h($e->getMessage()));
        }
        return;
    }

    if (str_starts_with($data, 'ep_parts:')) {
        $mid = (int) explode(':', $data)[1];
        sendEpisodeList($chatId, $mid, null);
        return;
    }
    if (str_starts_with($data, 'ep_part:')) {
        [, $mid, $prt] = explode(':', $data);
        sendEpisodeList($chatId, (int) $mid, (int) $prt);
        return;
    }
    if (str_starts_with($data, 'ep_get:')) {
        [, $mid, $epId] = explode(':', $data);
        deliverEpisode($userId, $chatId, (int) $mid, (int) $epId);
        return;
    }

    // ---- Admin panel callbacklari ----
    if (!isAdmin($userId)) {
        sendMessage($chatId, "⛔️ Sizda bu amalni bajarish uchun ruxsat yo'q.\n\nSizning Telegram ID'ingiz: <code>{$userId}</code>");
        return;
    }

    if ($data === 'adm_main') { admOpenSection('main', $userId, $chatId); return; }
    if ($data === 'adm_upload') { admOpenSection('upload', $userId, $chatId); return; }
    if (str_starts_with($data, 'up_type:')) {
        $type = explode(':', $data)[1];
        setState($userId, 'up_wait_movie', ['type' => $type]);
        sendMessage($chatId, $type === 'series' ? "🎬 Serialning 1-qism videosini (yoki hujjatini) yuboring." : "🎬 Kino faylini (video yoki hujjat) yuboring.");
        return;
    }
    if (str_starts_with($data, 'up_access:')) {
        $access = explode(':', $data)[1];
        $user = getUser($userId);
        $sd = getStateData($user);
        if (($sd['type'] ?? 'movie') === 'series') {
            finalizeSeriesUpload($userId, $chatId, $sd, $access);
        } else {
            finalizeMovieUpload($userId, $chatId, $sd, $access);
        }
        return;
    }
    if ($data === 'series_addmore') {
        $user = getUser($userId);
        $sd = getStateData($user);
        setState($userId, 'up_series_wait_ep', $sd);
        sendMessage($chatId, "🎬 Navbatdagi ({$sd['next_ep']}-) qism videosini yuboring.");
        return;
    }
    if ($data === 'series_publish') {
        $user = getUser($userId);
        $sd = getStateData($user);
        publishSeriesPost($userId, $chatId, $sd);
        return;
    }
    if ($data === 'adm_edit_movie') { admOpenSection('edit_movie', $userId, $chatId); return; }
    if (str_starts_with($data, 'admov_title:')) { setState($userId, 'admov_wait_newtitle', ['movie_id' => (int) explode(':', $data)[1]]); sendMessage($chatId, "Yangi nomni yuboring."); return; }
    if (str_starts_with($data, 'admov_code:')) { setState($userId, 'admov_wait_newcode', ['movie_id' => (int) explode(':', $data)[1]]); sendMessage($chatId, "Yangi kodni yuboring."); return; }
    if (str_starts_with($data, 'admov_desc:')) { setState($userId, 'admov_wait_newdesc', ['movie_id' => (int) explode(':', $data)[1]]); sendMessage($chatId, "Yangi tavsifni yuboring."); return; }
    if (str_starts_with($data, 'admov_addep:')) {
        $mid = (int) explode(':', $data)[1];
        $cntSt = db()->prepare('SELECT COALESCE(MAX(ep_number),0) FROM episodes WHERE movie_id=?');
        $cntSt->execute([$mid]);
        $nextEp = (int) $cntSt->fetchColumn() + 1;
        setState($userId, 'admov_wait_newep', ['movie_id' => $mid, 'next_ep' => $nextEp]);
        sendMessage($chatId, "🎬 {$nextEp}-qism videosini (yoki hujjatini) yuboring.");
        return;
    }
    if (str_starts_with($data, 'admov_acc:')) {
        $mid = (int) explode(':', $data)[1];
        $st = db()->prepare('SELECT access FROM movies WHERE id=?'); $st->execute([$mid]);
        $cur = $st->fetchColumn();
        $new = ($cur === 'vip') ? 'all' : 'vip';
        $u = db()->prepare('UPDATE movies SET access=? WHERE id=?'); $u->execute([$new, $mid]);
        sendMessage($chatId, $new === 'vip' ? "🌟 Endi bu kino faqat VIP foydalanuvchilar uchun." : "👥 Endi bu kino barcha uchun.");
        return;
    }
    if (str_starts_with($data, 'admov_del:')) {
        $mid = (int) explode(':', $data)[1];
        $st = db()->prepare('DELETE FROM movies WHERE id=?'); $st->execute([$mid]);
        $stEp = db()->prepare('DELETE FROM episodes WHERE movie_id=?'); $stEp->execute([$mid]);
        clearState($userId);
        sendMessage($chatId, "🗑 Kino o'chirildi.\n\n❗️ Eslatma: kino kodlari kanalidagi post avtomatik o'chmaydi, kerak bo'lsa uni qo'lda o'chiring.");
        return;
    }
    if ($data === 'adm_stats') { admStatsMenu($chatId); return; }
    if ($data === 'adm_stats_u') { admStatsUsersPeriods($chatId, $messageId); return; }
    if (str_starts_with($data, 'adm_su:')) { admStatsUsersShow($chatId, $messageId, explode(':', $data)[1]); return; }
    if ($data === 'adm_stats_c') { admStatsChannelsList($chatId, $messageId); return; }
    if (str_starts_with($data, 'adm_sc:')) { [, $cid, $per] = explode(':', $data); admStatsChannelShow($chatId, $messageId, (int) $cid, $per); return; }
    if ($data === 'adm_stats_m') { admStatsMoviesShow($chatId, $messageId); return; }

    if ($data === 'adm_channels') { admOpenSection('channels', $userId, $chatId); return; }
    if (str_starts_with($data, 'adm_ch_add:')) {
        $type = explode(':', $data)[1];
        $desc = channelTypeDescription($type);
        if ($type === 'public') {
            setState($userId, 'adm_ch_wait_id', ['type' => $type]);
            sendMessage($chatId, $desc . "\n\nKanalning @username'ini yuboring (masalan: @mychannel).");
        } elseif ($type === 'optional') {
            setState($userId, 'adm_ch_wait_link', ['type' => $type]);
            sendMessage($chatId, $desc . "\n\nTugma uchun havolani (link) yuboring.");
        } else {
            setState($userId, 'adm_ch_wait_id', ['type' => $type]);
            sendMessage($chatId, $desc . "\n\nKanal ID raqamini yuboring (masalan -1001234567890).\nID'ni bilmasangiz: kanaldan istalgan xabarni @getidsbot ga forward qiling.\n\n❗️ Bot shu kanalda ADMIN bo'lishi shart.");
        }
        return;
    }
    if (str_starts_with($data, 'adm_ch_del:')) { admChannelDelete((int) explode(':', $data)[1]); admChannelsList($chatId); return; }
    if (str_starts_with($data, 'adm_ch_edit:')) {
        $which = explode(':', $data)[1]; // storage | codes
        setState($userId, 'adm_ch_edit_wait_id', ['which' => $which]);
        $cur = $which === 'storage' ? storageChannelId() : codesChannelId();
        $label = $which === 'storage' ? "Kino baza kanali" : "Kino kodlari kanali";
        sendMessage($chatId, "✏️ {$label}\nJoriy: <code>" . h($cur) . "</code>\n\nYangi kanal ID yoki @username yuboring (masalan: -1001234567890 yoki @mychannel).\n\n❗️ Bot shu kanalda ADMIN bo'lishi shart.");
        return;
    }

    if ($data === 'adm_vip') { admOpenSection('vip', $userId, $chatId); return; }
    if ($data === 'adm_vip_add') { setState($userId, 'adm_vip_wait_name', []); sendMessage($chatId, "VIP reja nomini yuboring."); return; }
    if (str_starts_with($data, 'adm_vip_del:')) {
        $st = db()->prepare('DELETE FROM vip_plans WHERE id=?'); $st->execute([(int) explode(':', $data)[1]]);
        admVipList($chatId); return;
    }

    if ($data === 'adm_premium') { admOpenSection('premium', $userId, $chatId); return; }
    if ($data === 'adm_prem_add') { setState($userId, 'adm_prem_add_wait_id', []); sendMessage($chatId, "Premium qilinadigan foydalanuvchining Telegram ID raqamini yuboring."); return; }
    if ($data === 'adm_prem_del') { setState($userId, 'adm_prem_del_wait_id', []); sendMessage($chatId, "Premium bekor qilinadigan foydalanuvchining Telegram ID raqamini yuboring."); return; }

    if ($data === 'adm_payment') { admOpenSection('payment', $userId, $chatId); return; }
    if ($data === 'adm_pay_humo') { setState($userId, 'adm_pay_humo_wait_num', []); sendMessage($chatId, "Humo karta raqamini yuboring (bo'sh qoldirish uchun /skip)."); return; }
    if ($data === 'adm_pay_uzcard') { setState($userId, 'adm_pay_uzcard_wait_num', []); sendMessage($chatId, "Uzcard karta raqamini yuboring (bo'sh qoldirish uchun /skip)."); return; }
    if ($data === 'adm_pay_username') { setState($userId, 'adm_pay_username_wait', []); sendMessage($chatId, "Admin username'ni @ belgisisiz yuboring (masalan: myadmin)."); return; }

    if ($data === 'adm_limit') { admOpenSection('limit', $userId, $chatId); return; }
    if ($data === 'emoji_add') {
        setState($userId, 'adm_emoji_add_wait_emoji', []);
        sendMessage($chatId, "➕ Ro'yxatga qo'shmoqchi bo'lgan <b>oddiy emojini</b> yuboring (masalan: 🔥).\n\nKeyin shu emoji uchun kod ichida ishlatiladigan custom_emoji_id'ni so'rayman.");
        return;
    }
    if (str_starts_with($data, 'emoji_edit:')) {
        $emoji = substr($data, strlen('emoji_edit:'));
        setState($userId, 'adm_emoji_wait_id', ['emoji' => $emoji]);
        sendMessage($chatId, "Tanlangan emoji: {$emoji}\n\nYangi custom_emoji_id raqamini yuboring.\n\nO'chirish uchun /skip yozing (bu emoji standart holatga qaytadi).");
        return;
    }
    if ($data === 'toggle_ad_bypass') {
        $cur = (int) getSetting('ad_bypass_enabled', 0);
        setSetting('ad_bypass_enabled', (string) (1 - $cur));
        admOpenSection('limit', $userId, $chatId);
        return;
    }

    if ($data === 'adm_admins') { admOpenSection('admins', $userId, $chatId); return; }
    if ($data === 'adm_adm_add') { if (getRole($userId) === 'super') { setState($userId, 'adm_adm_wait_id', []); sendMessage($chatId, "Yangi admin Telegram ID sini yuboring."); } return; }
    if (str_starts_with($data, 'adm_adm_del:')) {
        if (getRole($userId) === 'super') {
            $st = db()->prepare('DELETE FROM admins WHERE telegram_id=?'); $st->execute([(int) explode(':', $data)[1]]);
            admAdminsList($chatId);
        }
        return;
    }
    if (str_starts_with($data, 'admrole:')) {
        $user = getUser($userId); $sd = getStateData($user);
        $role = explode(':', $data)[1];
        $ins = db()->prepare('INSERT OR REPLACE INTO admins (telegram_id, role, added_by, added_at) VALUES (?,?,?,?)');
        $ins->execute([$sd['new_admin_id'], $role, $userId, time()]);
        clearState($userId);
        sendMessage($chatId, "✅ Admin qo'shildi.");
        admAdminsList($chatId);
        return;
    }

    if ($data === 'adm_ads') { admReklamaMenu($chatId); return; }
    if ($data === 'adm_ads_menu') { admReklamaMenu($chatId); return; }
    if ($data === 'adm_ads_movie') { admAdsList($chatId, 'movie'); return; }
    if ($data === 'adm_ads_limit') { admAdsList($chatId, 'limit_bypass'); return; }

    if ($data === 'adm_chads_menu') { admChAdsMenu($chatId); return; }
    if ($data === 'chad_ch_add') {
        setState($userId, 'chad_ch_wait_id', []);
        sendMessage($chatId, "Kanal ID raqamini yuboring (masalan -1001234567890).\nID'ni bilmasangiz: kanaldan xabarni @getidsbot ga forward qiling.\n\n❗️ Bot shu kanalda ADMIN bo'lishi shart (postlarni ko'rish va o'chirish huquqi bilan).");
        return;
    }
    if (str_starts_with($data, 'chad_ch:')) { admChAdsChannelMenu($chatId, (int) explode(':', $data)[1]); return; }
    if (str_starts_with($data, 'chad_ch_toggle:')) {
        $id = (int) explode(':', $data)[1];
        db()->prepare('UPDATE promo_channels SET is_active = 1 - is_active WHERE id=?')->execute([$id]);
        admChAdsChannelMenu($chatId, $id);
        return;
    }
    if (str_starts_with($data, 'chad_ch_del:')) {
        $id = (int) explode(':', $data)[1];
        db()->prepare('DELETE FROM channel_ads WHERE promo_channel_id=?')->execute([$id]);
        db()->prepare('DELETE FROM promo_channel_state WHERE promo_channel_id=?')->execute([$id]);
        db()->prepare('DELETE FROM promo_channels WHERE id=?')->execute([$id]);
        admChAdsMenu($chatId);
        return;
    }
    if (str_starts_with($data, 'chad_add:')) {
        [, $mode, $pcId] = explode(':', $data);
        setState($userId, 'chad_wait_mode_content', ['ad_mode' => $mode, 'promo_channel_id' => (int) $pcId]);
        sendMessage($chatId, "Reklama turini tanlang:", ikb([
            [btn('✉️ Oddiy xabar', 'chad_content:normal', 'primary')],
            [btn('↪️ Forward xabar', 'chad_content:forward', 'primary')],
        ]));
        return;
    }
    if (str_starts_with($data, 'chad_content:')) {
        $cmode = explode(':', $data)[1];
        $user = getUser($userId); $sd = getStateData($user);
        $sd['content_mode'] = $cmode;
        if ($cmode === 'forward') {
            setState($userId, 'chad_wait_forward', $sd);
            sendMessage($chatId, "↪️ Forward qilmoqchi bo'lgan xabaringizni yuboring.");
        } else {
            setState($userId, 'chad_wait_content', $sd);
            sendMessage($chatId, "Reklama uchun matn, rasm, video yoki fayl yuboring.");
        }
        return;
    }
    if (str_starts_with($data, 'chad_view:')) { admChAdView($chatId, (int) explode(':', $data)[1]); return; }
    if (str_starts_with($data, 'chad_toggle:')) {
        $id = (int) explode(':', $data)[1];
        db()->prepare('UPDATE channel_ads SET is_active = 1 - is_active WHERE id=?')->execute([$id]);
        admChAdView($chatId, $id);
        return;
    }
    if (str_starts_with($data, 'chad_delprev_toggle:')) {
        $id = (int) explode(':', $data)[1];
        db()->prepare('UPDATE channel_ads SET auto_delete_prev = 1 - auto_delete_prev WHERE id=?')->execute([$id]);
        admChAdView($chatId, $id);
        return;
    }
    if (str_starts_with($data, 'chad_del:')) {
        $id = (int) explode(':', $data)[1];
        $p = db()->prepare('SELECT promo_channel_id FROM channel_ads WHERE id=?'); $p->execute([$id]); $pcId = $p->fetchColumn();
        db()->prepare('DELETE FROM channel_ads WHERE id=?')->execute([$id]);
        db()->prepare('DELETE FROM channel_ad_state WHERE channel_ad_id=?')->execute([$id]);
        db()->prepare('DELETE FROM channel_ad_sent_log WHERE channel_ad_id=?')->execute([$id]);
        if ($pcId) admChAdsChannelMenu($chatId, (int) $pcId); else admChAdsMenu($chatId);
        return;
    }
    if (str_starts_with($data, 'chad_edit_times:')) {
        $id = (int) explode(':', $data)[1];
        setState($userId, 'chad_wait_times', ['ad_id' => $id]);
        sendMessage($chatId, "Vaqtlarni yuboring (24 soatlik formatda, vergul bilan ajratib):\n\nMasalan: <code>08:00, 12:00, 18:30, 22:00</code>");
        return;
    }
    if (str_starts_with($data, 'ad_add:')) {
        $purpose = explode(':', $data)[1]; // movie | limit_bypass
        sendMessage($chatId, "🎥 Reklama turini tanlang:", ikb([
            [btn('✉️ Oddiy xabar', 'ad_mode:normal:' . $purpose, 'primary')],
            [btn('↪️ Forward xabar', 'ad_mode:forward:' . $purpose, 'primary')],
        ]));
        return;
    }
    if (str_starts_with($data, 'ad_mode:')) {
        [, $mode, $purpose] = explode(':', $data);
        if ($mode === 'forward') {
            setState($userId, 'ad_wait_forward', ['purpose' => $purpose, 'mode' => 'forward']);
            sendMessage($chatId, "↪️ Forward qilmoqchi bo'lgan xabaringizni yuboring.");
        } else {
            setState($userId, 'ad_wait_content', ['purpose' => $purpose, 'mode' => 'normal']);
            sendMessage($chatId, "🎥 Reklama uchun matn, rasm, video yoki fayl yuboring.");
        }
        return;
    }
    if (str_starts_with($data, 'ad_edit:')) {
        $id = (int) explode(':', $data)[1];
        $st = db()->prepare('SELECT * FROM ads WHERE id=?'); $st->execute([$id]);
        $ad = $st->fetch(PDO::FETCH_ASSOC);
        if (!$ad) { sendMessage($chatId, "❌ Topilmadi."); return; }
        sendMessage($chatId, "✏️ #{$id} reklamada nimani tahrirlaysiz?", ikb([
            [btn('⏱ Vaqtini', 'ad_editf:duration:' . $id, 'primary'), btn('🔢 Kodlarini', 'ad_editf:codes:' . $id, 'primary')],
            [btn('📝 Matnini', 'ad_editf:text:' . $id, 'primary')],
            [btn('⬅️ Orqaga', ($ad['purpose'] === 'limit_bypass' ? 'adm_ads_limit' : 'adm_ads_movie'), null, emIcon('⬅️'))],
        ]));
        return;
    }
    if (str_starts_with($data, 'ad_editf:')) {
        [, $field, $id] = explode(':', $data);
        $map = ['duration' => 'ad_edit_wait_duration', 'codes' => 'ad_edit_wait_codes', 'text' => 'ad_edit_wait_text'];
        setState($userId, $map[$field], ['ad_id' => (int) $id]);
        $prompts = ['duration' => "Yangi davomiylikni soniyada yuboring (masalan 10).", 'codes' => "Yangi kino kodlarini yuboring (masalan 1 yoki 4|6|7|8 yoki 'all').", 'text' => "Yangi matnni yuboring."];
        sendMessage($chatId, $prompts[$field]);
        return;
    }
    if (str_starts_with($data, 'ad_toggle:')) {
        $id = (int) explode(':', $data)[1];
        $p = db()->prepare('SELECT purpose FROM ads WHERE id=?'); $p->execute([$id]); $purpose = $p->fetchColumn();
        db()->prepare('UPDATE ads SET is_active = 1 - is_active WHERE id=?')->execute([$id]);
        admAdsList($chatId, $purpose ?: null);
        return;
    }
    if (str_starts_with($data, 'ad_del:')) {
        $id = (int) explode(':', $data)[1];
        $p = db()->prepare('SELECT purpose FROM ads WHERE id=?'); $p->execute([$id]); $purpose = $p->fetchColumn();
        db()->prepare('DELETE FROM ads WHERE id=?')->execute([$id]);
        admAdsList($chatId, $purpose ?: null);
        return;
    }
    if ($data === 'ad_codes_all') {
        $user = getUser($userId); $sd = getStateData($user);
        finalizeAd($userId, $chatId, $sd, 'all');
        return;
    }

    if ($data === 'adm_broadcast') { admOpenSection('broadcast', $userId, $chatId); return; }
    if ($data === 'bc_mode:forward') {
        setState($userId, 'bc_wait_forward', []);
        sendMessage($chatId, "↪️ Forward qilmoqchi bo'lgan xabarni menga yuboring (istalgan chatdan forward qiling).");
        return;
    }
    if ($data === 'bc_mode:normal') {
        setState($userId, 'bc_wait_content', []);
        sendMessage($chatId, "✉️ Yuboriladigan xabarni jo'nating (matn, rasm, video yoki fayl bo'lishi mumkin).");
        return;
    }
    if ($data === 'bc_confirm') {
        $user = getUser($userId); $sd = getStateData($user);
        if (!empty($sd['forward_message_id'])) runBroadcastForward($userId, $chatId, $sd);
        else runBroadcast($userId, $chatId, $sd);
        return;
    }
    if ($data === 'bc_cancel') { clearState($userId); sendMessage($chatId, "Bekor qilindi."); return; }
}

/* ------------------------- Xabar (message) ishlovchisi ------------------------- */

function handleMessage(array $msg): void {
    $from = $msg['from'];
    $userId = (int) $from['id'];
    $chatId = $msg['chat']['id'];
    $text = $msg['text'] ?? '';

    if (($msg['chat']['type'] ?? '') !== 'private') return; // faqat shaxsiy chat bilan ishlaymiz

    $user = upsertUser($userId, $from['username'] ?? null, trim(($from['first_name'] ?? '') . ' ' . ($from['last_name'] ?? '')));

    // Admin support xabariga "Reply" qilib javob bersa — javobni asl foydalanuvchiga yetkazamiz
    if (isAdmin($userId) && isset($msg['reply_to_message']) && $text !== '') {
        $rid = $msg['reply_to_message']['message_id'];
        $st = db()->prepare('SELECT user_id FROM support_messages WHERE admin_message_id=? AND admin_id=? ORDER BY id DESC LIMIT 1');
        $st->execute([$rid, $userId]);
        $targetUser = $st->fetchColumn();
        if ($targetUser) {
            tgApi('sendMessage', array_merge(['chat_id' => $targetUser], textPayload("💬 <b>Admin javobi:</b>\n\n" . h($text))));
            sendMessage($chatId, "✅ Javobingiz foydalanuvchiga yuborildi.");
            return;
        }
    }

    // /start (payload bilan yoki bo'lmasa)
    if (str_starts_with($text, '/start')) {
        clearState($userId);
        $parts = explode(' ', $text, 2);
        $payload = $parts[1] ?? '';
        if (str_starts_with($payload, 'movie_')) {
            $code = substr($payload, 6);
            // VIP foydalanuvchi yoki allaqachon barcha kanallarga a'zo bo'lgan
            // foydalanuvchi uchun to'g'ridan-to'g'ri kino/serial yetkaziladi.
            if (isVipActive($user) || empty(missingChannels($userId))) {
                attemptDeliverMovie($userId, $chatId, $code);
                return;
            }
            // Aks holda — kanallarga a'zo bo'lishga o'tkazishdan OLDIN foydalanuvchi
            // turini (Oddiy/VIP) tanlashini so'raymiz.
            setState($userId, 'pending_movie_code', ['code' => $code]);
            sendMessage($chatId, "🎬 Kinoni olishdan oldin, foydalanuvchi turini tanlang 👇", ikb([
                [btn('👍 Oddiy', 'menu_normal', 'primary', emIcon('👍')), btn('💎 VIP', 'menu_vip', 'primary', vipIcon())],
            ]));
            return;
        }
        // VIP foydalanuvchi yoki allaqachon barcha kanallarga obuna bo'lgan
        // foydalanuvchi uchun Oddiy/VIP menyusi ko'rsatilmaydi — to'g'ridan-to'g'ri
        // "kino kodini yuborishingiz mumkin" xabari chiqadi.
        if (isVipActive($user)) {
            sendCodePrompt($chatId, $userId);
            return;
        }
        if (empty(missingChannels($userId))) {
            sendCodePrompt($chatId, $userId);
            return;
        }
        sendStartMenu($chatId);
        return;
    }

    if ($text === '/admin') {
        if (isAdmin($userId)) adminMainMenu($chatId, $userId);
        else sendMessage($chatId, "⛔️ Sizda admin huquqi yo'q.");
        return;
    }

    // VIP pastki tugmalari (istalgan foydalanuvchi uchun, faqat VIP'ga ko'rsatiladi)
    if ($text === '🏆 TOP 10') { showTop10($chatId, $userId); return; }
    if ($text === '🎞 Saqlanganlarim') { showMySaved($chatId, $userId); return; }
    if ($text === '📊 Status') {
        if (!ensureSubscribedForBasicFeature($userId, $chatId)) return;
        showMyStatus($chatId, $userId);
        return;
    }
    if ($text === '🧑‍💻 Adminga murojaat') {
        if (!ensureSubscribedForBasicFeature($userId, $chatId)) return;
        setState($userId, 'support_wait_msg', []);
        sendMessage($chatId, "✍️ Xabaringizni yozing — men adminga yuboraman.");
        return;
    }

    // Admin panelining pastki (doimiy) tugmalari orqali bo'lim tanlash
    if (isAdmin($userId)) {
        if ($text === '⬅️ Panelni yopish') {
            clearState($userId);
            tgApi('sendMessage', ['chat_id' => $chatId, 'text' => 'Admin panel yopildi.', 'reply_markup' => json_encode(['remove_keyboard' => true])]);
            return;
        }
        $labelMap = adminMenuLabelMap();
        if (isset($labelMap[$text])) {
            admOpenSection($labelMap[$text], $userId, $chatId);
            return;
        }
    }

    // Admin bosqichma-bosqich holatlar (yuklash, kanal qo'shish va h.k.)
    if (isAdmin($userId) && !empty($user['state'])) {
        $state = $user['state'];
        if (in_array($state, ['up_wait_movie', 'up_wait_intro', 'up_series_wait_ep', 'admov_wait_newep'], true)) { handleUploadFlow($user, $msg); return; }
        if ($state === 'bc_wait_forward') {
            $fChatId = null; $fMsgId = null;
            // Yangi Bot API (forward_origin) va eski (forward_from_chat) formatlarini qo'llab-quvvatlaymiz
            if (isset($msg['forward_origin']['chat']['id'], $msg['forward_origin']['message_id'])) {
                $fChatId = $msg['forward_origin']['chat']['id'];
                $fMsgId = $msg['forward_origin']['message_id'];
            } elseif (isset($msg['forward_from_chat']['id'], $msg['forward_from_message_id'])) {
                $fChatId = $msg['forward_from_chat']['id'];
                $fMsgId = $msg['forward_from_message_id'];
            }
            if (!$fChatId || !$fMsgId) {
                // Forward qilib bo'lmaydigan (masalan, maxfiylik sozlamasi tufayli
                // "kimdan" ko'rsatilmaydigan) xabar bo'lsa — shu xabarning o'zini olib,
                // uni forward emas, copy qilib yuboramiz.
                $fChatId = $chatId;
                $fMsgId = $msg['message_id'];
            }
            $fdata = ['forward_chat_id' => $fChatId, 'forward_message_id' => $fMsgId];
            setState($userId, 'bc_wait_confirm', $fdata);
            tgApi('copyMessage', ['chat_id' => $chatId, 'from_chat_id' => $fChatId, 'message_id' => $fMsgId]);
            sendMessage($chatId, "Yuqoridagi xabar barcha foydalanuvchilarga forward qilinadi. Tasdiqlaysizmi?", ikb([
                [btn('✅ Yuborish', 'bc_confirm', 'success', emIcon('✅')), btn('❌ Bekor qilish', 'bc_cancel', 'danger', emIcon('❌'))],
            ]));
            return;
        }
        if ($state === 'bc_wait_content') {
            $bdata = null;
            if (isset($msg['photo'])) { $photos = $msg['photo']; $bdata = ['type' => 'photo', 'file_id' => end($photos)['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['video'])) { $bdata = ['type' => 'video', 'file_id' => $msg['video']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['document'])) { $bdata = ['type' => 'document', 'file_id' => $msg['document']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['text'])) { $bdata = ['type' => 'text', 'text' => $msg['text']]; }
            if (!$bdata) { sendMessage($chatId, "❌ Qo'llab-quvvatlanmaydigan format."); return; }
            setState($userId, 'bc_wait_button_text', $bdata);
            sendMessage($chatId, "Tugma matnini yuboring (kerak bo'lmasa \"yo'q\" deb yozing).");
            return;
        }
        if ($state === 'ad_wait_content') {
            $prevData = getStateData($user);
            $adata = null;
            if (isset($msg['photo'])) { $photos = $msg['photo']; $adata = ['content_type' => 'photo', 'file_id' => end($photos)['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['video'])) { $adata = ['content_type' => 'video', 'file_id' => $msg['video']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['document'])) { $adata = ['content_type' => 'document', 'file_id' => $msg['document']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['text'])) { $adata = ['content_type' => 'text', 'text' => $msg['text']]; }
            if (!$adata) { sendMessage($chatId, "❌ Qo'llab-quvvatlanmaydigan format."); return; }
            $adata['purpose'] = $prevData['purpose'] ?? 'movie';
            $adata['mode'] = 'normal';
            setState($userId, 'ad_wait_button_text', $adata);
            sendMessage($chatId, "Reklama tugmasi matnini yuboring (kerak bo'lmasa /skip deb yozing).");
            return;
        }
        if ($state === 'ad_wait_forward') {
            $prevData = getStateData($user);
            if (isset($msg['forward_origin']['chat']['id'], $msg['forward_origin']['message_id'])) {
                $fChatId = $msg['forward_origin']['chat']['id'];
                $fMsgId = $msg['forward_origin']['message_id'];
            } elseif (isset($msg['forward_from_chat']['id'], $msg['forward_from_message_id'])) {
                $fChatId = $msg['forward_from_chat']['id'];
                $fMsgId = $msg['forward_from_message_id'];
            } else {
                $fChatId = $chatId;
                $fMsgId = $msg['message_id'];
            }
            $adata = [
                'mode' => 'forward',
                'purpose' => $prevData['purpose'] ?? 'movie',
                'forward_chat_id' => $fChatId,
                'forward_message_id' => $fMsgId,
            ];
            setState($userId, 'ad_wait_duration', $adata);
            sendMessage($chatId, "Reklama necha soniya davom etsin? (masalan: 10)");
            return;
        }
        if ($state === 'chad_wait_content') {
            $prevData = getStateData($user);
            $cdata = null;
            if (isset($msg['photo'])) { $photos = $msg['photo']; $cdata = ['content_type' => 'photo', 'file_id' => end($photos)['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['video'])) { $cdata = ['content_type' => 'video', 'file_id' => $msg['video']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['document'])) { $cdata = ['content_type' => 'document', 'file_id' => $msg['document']['file_id'], 'text' => $msg['caption'] ?? '']; }
            elseif (isset($msg['text'])) { $cdata = ['content_type' => 'text', 'text' => $msg['text']]; }
            if (!$cdata) { sendMessage($chatId, "❌ Qo'llab-quvvatlanmaydigan format."); return; }
            $cdata = array_merge($prevData, $cdata);
            setState($userId, 'chad_wait_button_text', $cdata);
            sendMessage($chatId, "Tugma matnini yuboring (kerak bo'lmasa /skip deb yozing).");
            return;
        }
        if ($state === 'chad_wait_forward') {
            $prevData = getStateData($user);
            if (isset($msg['forward_origin']['chat']['id'], $msg['forward_origin']['message_id'])) {
                $fChatId = $msg['forward_origin']['chat']['id'];
                $fMsgId = $msg['forward_origin']['message_id'];
            } elseif (isset($msg['forward_from_chat']['id'], $msg['forward_from_message_id'])) {
                $fChatId = $msg['forward_from_chat']['id'];
                $fMsgId = $msg['forward_from_message_id'];
            } else {
                $fChatId = $chatId;
                $fMsgId = $msg['message_id'];
            }
            $cdata = $prevData;
            $cdata['forward_chat_id'] = $fChatId;
            $cdata['forward_message_id'] = $fMsgId;
            if ($cdata['ad_mode'] === 'top_post') {
                setState($userId, 'chad_wait_delay', $cdata);
                sendMessage($chatId, "So'nggi kanal postidan necha daqiqa o'tgach reklama yuborilsin? (masalan: 30)");
            } else {
                setState($userId, 'chad_wait_times', $cdata);
                sendMessage($chatId, "Vaqtlarni yuboring (24 soatlik formatda, vergul bilan ajratib):\n\nMasalan: <code>08:00, 12:00, 18:30, 22:00</code>");
            }
            return;
        }
        if (in_array($state, ['adm_startmsg_wait_photo', 'adm_codemsg_wait_photo', 'adm_expmsg_wait_photo'], true)) {
            $keyMap = [
                'adm_startmsg_wait_photo' => 'start_photo',
                'adm_codemsg_wait_photo' => 'code_prompt_photo',
                'adm_expmsg_wait_photo' => 'expired_photo',
            ];
            $settingKey = $keyMap[$state];
            if (isset($msg['text']) && trim($msg['text']) === '/skip') {
                setSetting($settingKey, '');
            } elseif (isset($msg['photo'])) {
                $photos = $msg['photo'];
                setSetting($settingKey, end($photos)['file_id']);
            } else {
                sendMessage($chatId, "❌ Rasm yuboring yoki /skip deb yozing.");
                return;
            }
            clearState($userId);
            sendMessage($chatId, "✅ Xabar yangilandi.");
            return;
        }
        if (processTextState($user, $msg)) return;
    }

    // VIP to'lov oqimi (har qanday oddiy foydalanuvchi uchun) — chek yuborilganda
    if (!empty($user['state']) && $user['state'] === 'vip_wait_receipt') {
        $sd = getStateData($user);
        $payId = (int) ($sd['payment_id'] ?? 0);
        $st0 = db()->prepare('SELECT * FROM vip_payments WHERE id=?');
        $st0->execute([$payId]);
        $pay = $st0->fetch(PDO::FETCH_ASSOC);
        if (!$pay || $pay['status'] !== 'awaiting_payment' || (int) $pay['reserved_until'] < time()) {
            sendMessage($chatId, "⏳ Bu to'lov muddati tugagan. Iltimos, qaytadan VIP rejani tanlang.");
            clearState($userId);
            return;
        }

        $fileId = null; $fileType = null;
        if (isset($msg['photo'])) { $photos = $msg['photo']; $fileId = end($photos)['file_id']; $fileType = 'photo'; }
        elseif (isset($msg['document'])) { $fileId = $msg['document']['file_id']; $fileType = 'document'; }
        if (!$fileId) { sendMessage($chatId, "❌ Iltimos, chekni rasm yoki fayl ko'rinishida yuboring."); return; }

        $upd = db()->prepare("UPDATE vip_payments SET receipt_file_id=?, receipt_type=?, status='pending' WHERE id=?");
        $upd->execute([$fileId, $fileType, $payId]);

        $stp = db()->prepare('SELECT * FROM vip_plans WHERE id=?');
        $stp->execute([$pay['plan_id']]);
        $plan = $stp->fetch(PDO::FETCH_ASSOC);

        $displayName = trim(($from['first_name'] ?? '') . ' ' . ($from['last_name'] ?? ''));
        $caption = "🆕 <b>Yangi VIP to'lov so'rovi</b>\n\n👤 " . h($displayName) . "\n🆔 <code>{$userId}</code>";
        if (isset($from['username']) && $from['username']) $caption .= " (@" . h($from['username']) . ")";
        $caption .= "\n💎 Reja: " . h($plan['name'] ?? '') . "\n💳 Usul: " . h($pay['method'] ?? '') . "\n💰 Kutilayotgan summa: <code>{$pay['exact_amount']}</code> so'm\n";
        $kb = ikb([[btn('✅ Tasdiqlash', 'vip_approve:' . $payId, 'success', emIcon('✅')), btn('❌ Rad etish', 'vip_reject:' . $payId, 'danger', emIcon('❌'))]]);

        $adminIds = array_merge([SUPER_ADMIN_ID], db()->query('SELECT telegram_id FROM admins')->fetchAll(PDO::FETCH_COLUMN));
        foreach (array_unique($adminIds) as $aid) {
            if ($fileType === 'photo') tgApi('sendPhoto', array_merge(['chat_id' => $aid, 'photo' => $fileId, 'reply_markup' => json_encode($kb)], captionPayload($caption)));
            else tgApi('sendDocument', array_merge(['chat_id' => $aid, 'document' => $fileId, 'reply_markup' => json_encode($kb)], captionPayload($caption)));
        }

        clearState($userId);
        sendMessage($chatId, "✅ Chekingiz qabul qilindi va adminga yuborildi. Tasdiqlanishini kuting.");
        return;
    }

    if (!empty($user['state']) && $user['state'] === 'await_sub_then_menu') {
        sendMessage($chatId, "Iltimos, avval yuqoridagi \"✅ Tekshirish\" tugmasini bosing.");
        return;
    }
    if (!empty($user['state']) && $user['state'] === 'await_sub_then_movie') {
        sendMessage($chatId, "Iltimos, avval yuqoridagi \"✅ Tekshirish\" tugmasini bosing.");
        return;
    }

    if (!empty($user['state']) && $user['state'] === 'support_wait_msg') {
        if ($text === '') { sendMessage($chatId, "❌ Iltimos, matn ko'rinishida yozing."); return; }
        $displayName = trim(($from['first_name'] ?? '') . ' ' . ($from['last_name'] ?? ''));
        $header = "🧑‍💻 <b>Yangi murojaat</b>\n\n👤 " . h($displayName);
        if (!empty($from['username'])) $header .= " (@" . h($from['username']) . ")";
        $header .= "\n🆔 <code>{$userId}</code>\n\n💬 " . h($text);
        $header .= "\n\n↩️ Javob berish uchun shu xabarga <b>Reply</b> qiling.";
        $adminIds = array_merge([SUPER_ADMIN_ID], db()->query('SELECT telegram_id FROM admins')->fetchAll(PDO::FETCH_COLUMN));
        foreach (array_unique($adminIds) as $aid) {
            $r = tgApi('sendMessage', array_merge(['chat_id' => $aid], textPayload($header)));
            if ($r && !empty($r['ok'])) {
                $ins = db()->prepare('INSERT INTO support_messages (user_id, admin_id, admin_message_id, created_at) VALUES (?,?,?,?)');
                $ins->execute([$userId, $aid, $r['result']['message_id'], time()]);
            }
        }
        clearState($userId);
        sendMessage($chatId, "✅ Xabaringiz adminga yuborildi. Tez orada javob olasiz.");
        return;
    }

    // oddiy holatda: kino kodi sifatida qabul qilish
    $code = trim($text);
    if ($code !== '') { attemptDeliverMovie($userId, $chatId, $code); return; }
}

/* ------------------------- Kanalga qo'shilish so'rovi ------------------------- */

function handleJoinRequest(array $jr): void {
    $chatId = $jr['chat']['id'];
    $userId = (int) $jr['from']['id'];
    $st = db()->prepare('SELECT id FROM channels WHERE channel_id=? OR channel_id=?');
    $uname = isset($jr['chat']['username']) ? '@' . $jr['chat']['username'] : '';
    $st->execute([(string) $chatId, $uname]);
    $chId = $st->fetchColumn();
    if ($chId) logChannelEvent((int) $chId, $userId, 'join_request');
}

/* ------------------------- Bot bloklanishi/qayta ishga tushishi ------------------------- */

function handleMyChatMember(array $m): void {
    if (($m['chat']['type'] ?? '') !== 'private') return;
    $userId = (int) $m['chat']['id'];
    $status = $m['new_chat_member']['status'] ?? '';
    if ($status === 'kicked') {
        $st = db()->prepare('UPDATE users SET is_blocked=1 WHERE telegram_id=?');
        $st->execute([$userId]);
        logUserEvent($userId, 'blocked');
    } elseif ($status === 'member') {
        $st = db()->prepare('UPDATE users SET is_blocked=0 WHERE telegram_id=?');
        $st->execute([$userId]);
    }
}

/* ===================== 9) CRON (rejalashtirilgan vazifalar) ===================== */

function runCron(): void {
    $now = time();
    // 1) 24 soat o'tgan kino xabarlarini o'chirish, o'rniga eslatma qoldirish
    $expText = getSetting('expired_text', "⏳ Bu kinoning muddati tugadi va o'chirildi.\n\n💎 Kinolar o'chirilmasligini xohlasangiz — VIP obunaga o'ting!");
    $expPhoto = getSetting('expired_photo', '');
    $expKb = ikb([[btn('💎 VIP bo\'lish', 'menu_vip', 'primary', vipIcon())]]);

    $st = db()->prepare('SELECT * FROM movie_deliveries WHERE deleted=0 AND delete_at <= ? LIMIT 200');
    $st->execute([$now]);
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $row) {
        tgApi('deleteMessage', ['chat_id' => $row['chat_id'], 'message_id' => $row['message_id']]);
        if ($expPhoto) {
            tgApi('sendPhoto', array_merge(['chat_id' => $row['chat_id'], 'photo' => $expPhoto, 'reply_markup' => json_encode($expKb)], captionPayload($expText)));
        } else {
            tgApi('sendMessage', array_merge(['chat_id' => $row['chat_id'], 'reply_markup' => json_encode($expKb)], textPayload($expText)));
        }
        $u = db()->prepare('UPDATE movie_deliveries SET deleted=1 WHERE id=?');
        $u->execute([$row['id']]);
    }
    // 2) muddati tugagan VIP larni bekor qilish — avval kimlarga tegishli
    // ekanini olib qolamiz, so'ng bekor qilib, har biriga xabar yuboramiz
    // ("qayta obuna bo'lish" tugmasi bilan).
    $stExp = db()->prepare('SELECT telegram_id FROM users WHERE is_vip=1 AND vip_until <= ?');
    $stExp->execute([$now]);
    $expiredUserIds = $stExp->fetchAll(PDO::FETCH_COLUMN);

    $st2 = db()->prepare('UPDATE users SET is_vip=0 WHERE is_vip=1 AND vip_until <= ?');
    $st2->execute([$now]);

    if (!empty($expiredUserIds)) {
        $vipExpiredKb = ikb([[btn('💎 Qayta obuna bo\'lish', 'menu_vip', 'primary', vipIcon())]]);
        foreach ($expiredUserIds as $eid) {
            tgApi('sendMessage', array_merge(['chat_id' => $eid, 'reply_markup' => json_encode($vipExpiredKb)], textPayload("⏳ Sizning 💎 VIP obunangiz muddati tugadi.\n\nQayta obuna bo'lib, barcha imkoniyatlardan yana foydalanishingiz mumkin.")));
        }
    }

    // 3) 10 daqiqa ichida to'lanmagan VIP so'rovlarini bekor qilib, foydalanuvchiga xabar berish
    $adminUsername = getSetting('admin_username', '');
    $extra = $adminUsername ? " (@" . $adminUsername . ")" : '';
    $st3 = db()->prepare("SELECT * FROM vip_payments WHERE status='awaiting_payment' AND reserved_until <= ?");
    $st3->execute([$now]);
    foreach ($st3->fetchAll(PDO::FETCH_ASSOC) as $p) {
        tgApi('sendMessage', ['chat_id' => $p['user_id'], 'text' => "⏳ To'lov vaqti (10 daqiqa) tugagani sababli bekor qilindi.\n\nAgar to'lov qilgan bo'lsangiz-u ulgurmagan bo'lsangiz, adminga murojaat qiling{$extra}. Aks holda qaytadan VIP tanlashingiz mumkin.", 'parse_mode' => 'HTML']);
        $upd = db()->prepare("UPDATE vip_payments SET status='expired' WHERE id=?");
        $upd->execute([$p['id']]);
    }

    // 4) Kanalga yuboriluvchi reklamalar (top-post va vaqtli)
    try { processChannelAds(); } catch (Throwable $e) {
        @file_put_contents(__DIR__ . '/error.log', date('Y-m-d H:i:s') . ' processChannelAds: ' . $e->getMessage() . "\n", FILE_APPEND);
    }

    echo "cron ok " . date('Y-m-d H:i:s');
}

/* ===================== 10) KIRISH NUQTASI ===================== */

if (isset($_GET['cron'])) {
    if ($_GET['cron'] === CRON_SECRET_KEY) { runCron(); }
    else { http_response_code(403); echo 'forbidden'; }
    exit;
}

$rawInput = file_get_contents('php://input');
$update = json_decode($rawInput, true);

if (!is_array($update)) { http_response_code(200); echo 'ok'; exit; }

try {
    if (isset($update['message'])) {
        handleMessage($update['message']);
    } elseif (isset($update['callback_query'])) {
        handleCallback($update['callback_query']);
    } elseif (isset($update['chat_join_request'])) {
        handleJoinRequest($update['chat_join_request']);
    } elseif (isset($update['my_chat_member'])) {
        handleMyChatMember($update['my_chat_member']);
    } elseif (isset($update['channel_post'])) {
        handleChannelPost($update['channel_post']);
    }
} catch (Throwable $e) {
    // Xatolik bo'lsa botni to'xtatib qo'ymaslik uchun jimgina log qilamiz
    @file_put_contents(__DIR__ . '/error.log', date('Y-m-d H:i:s') . ' ' . $e->getMessage() . "\n", FILE_APPEND);
}

http_response_code(200);
echo 'ok';
