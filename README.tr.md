# Wraith W75 Profile Changer

Bir oyuna odaklandığında Wraith W75 klavyeni otomatik olarak oyun profiline, başka bir uygulamaya geçtiğinde normal profiline alır. Sistem tepsisinde sessizce çalışır.

[English README](README.md)

> Bu, resmi olmayan bir topluluk aracıdır. Wraith'in ya da klavyeyi üretenlerin onayı veya bağlantısı yoktur.

## Sorun

[wraith.software](https://wraith.software) yapılandırma sitesi profillerini klavyede değil, tarayıcıda tutar. Profil değiştirmek için siteyi açıp klavyeyi bağlaman ve profile kendin tıklaman gerekir. Oyunlar için farklı ışık, tuş ataması ya da tetikleme ayarı kullanıyorsan, bir oyunu her açıp kapattığında bunu tekrar yapmak zorundasın.

## Bu araç ne yapar

- Hangi uygulamanın odakta olduğunu izler.
- Öndeki pencere bir oyunsa oyun profilini klavyeye yükler.
- Başka bir uygulamaya (Alt+Tab, masaüstü, tarayıcı) geçince normal profilini tekrar yükler.
- Hangi uygulamaların oyun sayılacağını küçük bir ayarlar penceresinden seçmeni sağlar.
- Windows ile başlar ve sistem tepsisinde durur (normal profilde gri, oyun profilinde yeşil simge).

Klavyeyle USB HID üzerinden doğrudan konuştuğu için tarayıcının açık kalması gerekmez.

## Nasıl çalışır

Bu klavyede sitede bir profile geçmek, o profilin tüm yapılandırmasını klavyeye 64 baytlık HID raporları olarak (yaklaşık 120 adet) yüklemek demektir. Bu araç, sitede bir profile tıkladığında giden bu rapor dizisini bir kez kaydeder ve `profiles.json` dosyasında saklar. Sonra odaklı uygulama değiştikçe kaydedilen raporları yeniden oynatır.

Raporlar bir anlık görüntü olduğu için, bir profili sitede değiştirdikten sonra yeniden kaydetmen gerekir. Ayarlar penceresinde bunun için adım adım bir sihirbaz vardır.

## Gereksinimler

- Windows 10 veya 11
- Python 3.10 ya da üstü (Python 3.14 ile geliştirildi ve test edildi)
- USB kabloyla bağlı bir Wraith W75
- Tek seferlik profil kaydı için Chromium tabanlı bir tarayıcı (Chrome, Edge), çünkü site WebHID kullanır

Yalnızca USB kablolu Wraith W75 ile test edildi. Aynı yapılandırma arayüzünü (HID usage page `0xFF1B`, usage `0x91`) sunan diğer Wraith modelleri çalışabilir ama denenmedi. Kablosuz modlar denenmedi.

## Kurulum

```bash
git clone https://github.com/cankamer/Wraith-W75-Profile-Changer.git
cd Wraith-W75-Profile-Changer
pip install -r requirements.txt
```

Konsol penceresi açmadan başlatmak için `start.bat` dosyasına çift tıkla ya da şunu çalıştır:

```bash
pythonw wraith_auto.py
```

Sistem tepsisinde gri bir "W" simgesi belirir (gizli simgeler bölümünde olabilir).

## İlk kurulum

Uygulama hazır profillerle gelmez, çünkü profil senin klavye ayarına özeldir. İki profil kaydetmen gerekir:

1. Tepsi simgesine çift tıklayıp ayarlar penceresini aç.
2. **Klavye profilleri** bölümünde **Game profili** satırındaki **Tanımla...** düğmesine bas.
3. Sihirbazı izle:
   1. Verilen düğmeyle siteyi aç ve Connect ile klavyeni bağla.
   2. Sitede oyun için kullanacağın profili ayarla (ışık, tuşlar vb.).
   3. Sitede `F12`'ye bas, **Console** sekmesini aç, düğmeyle kodu kopyala, konsola yapıştırıp Enter'a bas. Chrome önce `allow pasting` yazmanı isterse yaz. Yerel ağ erişimi izni sorarsa izin ver.
   4. Sitenin sol menüsünde önce normal profiline, sonra oyun profiline tıkla.
   5. Sihirbaz yakalanan paket sayısını gösterince **Kaydet**'e bas.
4. **Normal profil** için aynısını tekrarla. Bu sefer önce oyun profiline, sonra normal profiline tıkla.
5. Oyunlarını eklemek için **Uygulama seç...** ya da **Çalışanlardan seç...** düğmesini kullan, ya da otomatik algılamayı açık bırak.
6. Oturum açıldığında çalışmasını istiyorsan **Windows ile birlikte başlat** kutusunu işaretle.

Geçişi istediğin zaman şu komutla sınayabilirsin:

```bash
python wraith_auto.py --test
```

Oyun profilini yükler, dört saniye bekler ve normal profili tekrar yükler. Sitede oyun profilinin ışığını değiştirdiysen, klavyede değiştiğini görürsün.

## Günlük kullanım

Tepsi simgesi menüsü:

| Öğe | Anlamı |
| --- | --- |
| Durum satırı | Şu anki profil ve onu tetikleyen uygulama |
| Ayarlar... | Ayarlar penceresini açar (çift tıklayınca da açılır) |
| Otomatik | Odaklı uygulamayı izler (varsayılan) |
| Oyun profili (elle) | Oyun profilini zorlar |
| Normal profil (elle) | Normal profili zorlar |
| Windows ile başlat | Uygulamayı Windows başlangıcına ekler ya da çıkarır |
| Çıkış | Uygulamayı kapatır |

Ayarlar penceresinde `.exe` dosyası seçerek ya da çalışan programlardan seçerek uygulama ekleyebilir, kaldırabilir, iki profili yeniden tanımlayabilir, otomatik algılamayı ve başlangıçta çalışmayı açıp kapatabilirsin.

### Oyun nasıl tanınır

Odaklı pencerenin sahibi olan uygulama şu durumlardan birinde oyun sayılır:

- Exe adı `games` listesindedir (örneğin `cs2.exe`).
- Otomatik algılama açıktır ve exe yolu `game_path_patterns` içindeki klasörlerden birini içerir (varsayılan olarak Steam `steamapps/common`, Epic Games, Riot Games ve Battle.net).

Steam, Epic başlatıcısı ve Wallpaper Engine gibi başlatıcılar ve yardımcı süreçler yok sayılır. Yönetici olarak çalışan oyunlar yollarını göstermeyebilir, onları adıyla `games` listesine ekle.

## Yapılandırma

Ayarlar ilk çalıştırmada oluşturulan `config.json` dosyasında tutulur. Değişiklikler yeniden başlatmadan, bir saniye içinde uygulanır.

| Anahtar | Varsayılan | Açıklama |
| --- | --- | --- |
| `game_profile` | `"game"` | `profiles.json` içindeki oyun profilinin adı |
| `normal_profile` | `"default"` | `profiles.json` içindeki normal profilin adı |
| `poll_seconds` | `0.5` | Odaklı pencerenin ne sıklıkla kontrol edileceği |
| `stable_polls` | `2` | Geçişten önce odağın kaç kontrol boyunca aynı kalacağı |
| `min_switch_seconds` | `4` | İki profil yüklemesi arasındaki en kısa süre |
| `auto_detect` | `true` | Bilinen oyun klasörlerindeki programları oyun say |
| `games` | `[]` | Her zaman oyun sayılacak exe adları |
| `game_path_patterns` | dosyaya bak | Oyun klasörünü belirten yol parçaları (`/` kullan) |
| `ignore_names` | dosyaya bak | Hiçbir zaman oyun sayılmayacak exe'ler |
| `ignore_path_parts` | dosyaya bak | Hiçbir zaman oyun sayılmayacak yol parçaları |

## Güvenlik önlemleri

Profil yüklemek, klavyenin yapılandırmasını yaklaşık bir buçuk saniye boyunca yeniden yazar. Yazmana karışma ihtimalini azaltmak için araç:

- Yüklemeden önce hiçbir tuşa basılı olmamasını bekler (beş saniye sonra yine de yükler).
- İki yükleme arasında en az `min_switch_seconds` bekler.
- Odağın bir an sabit kalmasını ister, böylece Alt+Tab sırasında hızlıca geçilen pencereler yüklemeyi tetiklemez.

Bir tuş yanıt vermemeye başlarsa, klavyeyi çıkarıp takmak normal durumunu geri getirir.

## Gizlilik ve güvenlik

- Araç yalnızca odaklı pencerenin sahibi olan sürecin adını ve yolunu okur. Oyunlara kod enjekte etmez, oyun belleğini okumaz, tuş vuruşlarını kaydetmez.
- İnternete hiçbir şey gönderilmez. Klavyeyle tüm iletişim yerel USB HID üzerindendir.
- Profil kayıt sihirbazı açıkken araç `127.0.0.1:8765` adresini dinler. Dinleyici sihirbaz kapanınca durur, her sihirbaz oturumu için üretilen rastgele bir anahtar kullanır ve yalnızca `Origin` değeri `https://wraith.software` olan istekleri kabul eder. Başka web siteleri ona veri gönderemez.
- Tarayıcı konsoluna yapıştırdığın kod yalnızca sitenin klavyeye gönderdiği raporları ve yalnızca bu yerel dinleyiciye iletir.
- `profiles.json` klavye yapılandırmanı, `config.json` oyun listeni içerir. İkisi de sürüm kontrolünün dışında tutulur.

## Sorun giderme

**Tepsi durumunda eksik profil hatası görünüyor.** Önce ayarlar penceresinden iki profili de tanımla (İlk kurulum bölümüne bak).

**Klavye bulunamadı.** USB kabloyla bağlı olduğundan ve başka bir programın onu tekelinde tutmadığından emin ol. `log.txt` geçişleri ve hataları kaydeder.

**Bir oyun algılanmıyor.** Oyuna odaklan, ayarlar penceresini aç, **Çalışanlardan seç...** ile ekle. Ya da exe adını `config.json` içindeki `games` listesine yaz.

**Oyun profili eski görünüyor.** Kaydettikten sonra sitede değiştirdin. Sihirbazla yeniden kaydet.

**Sihirbaza hiçbir şey ulaşmıyor.** Kodu `wraith.software` sekmesinin konsoluna yapıştırdığını, o sayfada klavyenin bağlı olduğunu ve yapıştırdıktan sonra bir profile tıkladığını kontrol et.

## Dosyalar

| Dosya | Amacı |
| --- | --- |
| `wraith_auto.py` | Tepsi uygulaması, odak izleyici, ayarlar penceresi ve klavye iletişimi |
| `profile_capture.py` | Profil kayıt sihirbazının kullandığı yerel dinleyici |
| `start.bat` | Uygulamayı konsol penceresi olmadan başlatır |
| `requirements.txt` | Python bağımlılıkları |
| `config.json` | Ayarların (ilk çalıştırmada oluşur, depoya eklenmez) |
| `profiles.json` | Kaydettiğin profiller (sihirbaz oluşturur, depoya eklenmez) |
| `log.txt` | Profil geçiş kaydı (depoya eklenmez) |

## Sorumluluk reddi

Bu araç klavyene ham yapılandırma raporları gönderir. Resmi sitenin gönderdiğini birebir tekrar oynatır, ancak olduğu gibi, herhangi bir garanti olmadan sunulur. Kullanım sorumluluğu sana aittir.

## Lisans

MIT. Bkz. [LICENSE](LICENSE).
