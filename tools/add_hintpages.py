#!/usr/bin/env python3
"""One-off: add the VR HINTS page table (titles + bodies) to ru/ui2.json."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "ru" / "ui2.json"
doc = json.loads(path.read_text(encoding="utf-8"))

pages = [
    dict(
        index=0,
        orig_title="Basics",
        ru_title="ОСНОВЫ",
        orig="PAUSE MENU\n\n<tab>Press the menu button or right trackpad.\n\nRECENTER\n\n<tab>Hold the menu button.\n\nVR SETTINGS\n\n<tab>In the main or pause menu, click Options, then VR. Allows configuring VR-specific settings and the mod's behavior.\n\n",
        ru="МЕНЮ ПАУЗЫ\n\n<tab>Нажмите кнопку меню или правый трекпад.\n\nЦЕНТРОВКА\n\n<tab>Удерживайте кнопку меню.\n\nНАСТРОЙКИ VR\n\n<tab>В главном меню или меню паузы откройте Настройки, затем VR. Здесь настраиваются параметры VR и поведение мода.\n\n",
    ),
    dict(
        index=1,
        orig_title="Movement",
        ru_title="ДВИЖЕНИЕ",
        orig="WALKING\n\n<tab>Move your left thumbstick (<stick_left>) in the direction you want to go.\n\nTURNING\n\n<tab>Press or hold <xpad_right_thumb_left> or <xpad_right_thumb_right> to turn in the desired direction. You can switch between snap and smooth turning in Options - VR - Movement.\n\nRUNNING\n\n<tab>Double-tap <sprint> and keep holding it.\n\nJUMPING\n\n<tab>To jump, press <jump>.\n\nCROUCHING\n\n<tab><Press:crouch_toggle>, or crouch in real life. You can change crouching options in Options - VR - Movement.\n\n",
        ru="ХОДЬБА\n\n<tab>Отклоняйте левый стик (<stick_left>) в нужную сторону.\n\nПОВОРОТЫ\n\n<tab>Нажимайте или удерживайте <xpad_right_thumb_left> или <xpad_right_thumb_right>, чтобы поворачиваться в нужную сторону. Переключение между резким и плавным поворотом – в Настройки – VR – Движение.\n\nБЕГ\n\n<tab>Дважды нажмите <sprint> и продолжайте удерживать.\n\nПРЫЖКИ\n\n<tab>Чтобы прыгнуть, нажмите <jump>.\n\nПРИСЕДАНИЕ\n\n<tab><Press:crouch_toggle> или присядьте в реальной жизни. Настройки приседания – в Настройки – VR – Движение.\n\n",
    ),
    dict(
        index=2,
        orig_title="Interactions",
        ru_title="ВЗАИМОДЕЙСТВИЯ",
        orig="INTERACTIONS\n\n<tab>To interact with world objects (e.g. doors, ladders) or perform an action (e.g. take loot, grab/swap weapon), reach out with either hand and grip (<grip_dominant> or <grip_nondominant>).\n\n<tab>In some cases you will be offered a choice (e.g. lethal vs non-lethal takedowns, take/swap weapon or just take its parts) - in such cases you can choose by either gripping with that hand (<grip_dominant> or <grip_nondominant>) or pressing/holding a trigger (<trigger_dominant> or <trigger_nondominant>).\n\nQTEs\n\n<tab>Throughout the game you will encounter quick-time events. During them - depending on your game's settings - you will have to press, hold or quickly tap the <rui> button.\n\n",
        ru="ВЗАИМОДЕЙСТВИЯ\n\n<tab>Чтобы взаимодействовать с объектами мира (например, дверями, лестницами) или выполнить действие (взять добычу, схватить или сменить оружие), потянитесь любой рукой и схватите (<grip_dominant> или <grip_nondominant>).\n\n<tab>Иногда вам предложат выбор (например, смертельное или несмертельное устранение, взять или сменить оружие либо забрать только его части) – в таких случаях выбирайте хватом (<grip_dominant> или <grip_nondominant>) либо нажатием или удержанием триггера (<trigger_dominant> или <trigger_nondominant>).\n\nБЫСТРЫЕ СОБЫТИЯ\n\n<tab>По ходу игры вам будут встречаться быстрые события. В зависимости от настроек игры в них нужно нажимать, удерживать или быстро многократно нажимать кнопку <rui>.\n\n",
    ),
    dict(
        index=3,
        orig_title="Weapons",
        ru_title="ОРУЖИЕ",
        orig="STORAGE\n\n<tab>Weapons you carry can be grabbed from over your shoulders and from your <dominant> hip:\n\n* main weapon - over <dominant> shoulder\n* secondary weapon - <dominant> hip\n* special weapon - over <nondominant> shoulder\n\nEQUIPPING\n\n<tab>To grab a weapon you will have to grip the holster area with your <dominant> hand (<grip_dominant>). Once equipped you can grab its main handle or foregrip with your <nondominant> hand for stabilization and easier aiming.\n\nMODES / POSES\n\n<tab>The mod switches the weapon between normal, Aim Down Sights (ADS, for more accurate aiming) and Holstered (e.g. for faster running) modes based on how you hold it. Lower the weapon to holster it, or bring it up to your eyes to aim down sights.\n\nTHROWABLES\n\n<tab>Throwables you find or craft (decoys, knives, molotovs, grenades) go on your belt in front of you. Switch between them with <trigger_nondominant>, or grab them with <grip_dominant> or <grip_nondominant>.[ <Press:wpn_dynamite> to throw the selected one.]\n\nWEAPONS AND AMMO\n\n<tab>Hold <popup_equipment> to see your weapons and ammunition. While holding it, press <rui> to switch the ammunition type of the weapon in your hands (see Manual reloading).\n\nMELEE\n\n<tab>Press <wpn_fast_knife>.\n\n",
        ru="ХРАНЕНИЕ\n\n<tab>Носимое оружие можно достать из-за плеча и с <dominant> бедра:\n\n* основное оружие – из-за <dominant> плеча\n* запасное оружие – с <dominant> бедра\n* особое оружие – из-за <nondominant> плеча\n\nЭКИПИРОВКА\n\n<tab>Чтобы взять оружие, схватите область кобуры <dominant> рукой (<grip_dominant>). Взяв его, можно взяться <nondominant> рукой за основную рукоять или цевье для стабилизации и более удобного прицеливания.\n\nРЕЖИМЫ И ПОЛОЖЕНИЯ\n\n<tab>В зависимости от того, как вы держите оружие, мод переключает его между обычным режимом, прицеливанием (ADS, для более точной стрельбы) и убранным положением (например, для быстрого бега). Опустите оружие, чтобы убрать его, или поднесите к глазам, чтобы прицелиться.\n\nМЕТАТЕЛЬНЫЕ ПРЕДМЕТЫ\n\n<tab>Найденные или созданные метательные предметы (приманки, ножи, коктейли Молотова, гранаты) крепятся на поясе спереди. Переключайтесь между ними с помощью <trigger_nondominant> или берите их <grip_dominant> либо <grip_nondominant>.[ <Press:wpn_dynamite>, чтобы бросить выбранный.]\n\nОРУЖИЕ И БОЕПРИПАСЫ\n\n<tab>Удерживайте <popup_equipment>, чтобы увидеть оружие и боеприпасы. Удерживая ее, нажмите <rui>, чтобы сменить тип боеприпасов оружия в руках (см. Ручная перезарядка).\n\nБЛИЖНИЙ БОЙ\n\n<tab>Нажмите <wpn_fast_knife>.\n\n",
    ),
    dict(
        index=4,
        orig_title="Manual reloading",
        ru_title="РУЧНАЯ ПЕРЕЗАРЯДКА",
        orig="MANUAL RELOADING\n\n<tab>Most weapons will require you to perform these actions with <trigger_nondominant>:\n\n* remove old magazine\n* grab a new magazine from the pouch (<nondominant> hip or chest) and insert it\n* optionally pull the bolt\n\nSome weapons might have special needs such as:\n\n* pushing the magazine through the weapon before you can take it out\n* pulling a lever to release the magazine or chamber a new slug\n* drawing the bow before inserting an arrow\n* pumping the pneumatic system (see below)\n\n<tab>If you're unsure what to do, enable PART HIGHLIGHTS in Options - VR - Weapons. It highlights the next part you need to work to reload the weapon.\n\nPNEUMATIC WEAPONS\n\n<tab>Tikhar, Helsing and Gatling need pressure. Pump manually with your <nondominant> hand: take the pump handle with <trigger_nondominant> and pump it back and forth; it lets go by itself when full. Or hold <rui> and tap <wpn_fire>.\n\nSPECIAL AMMUNITION\n\n<tab>Tikhar can fire Incendiary Ammunition and Helsing explosive bolts. With the weapon in your hands, hold <popup_equipment> and press <rui> at the same time. A pulse confirms that your next reload loads the other ammunition; reload by hand as usual. Do it again to cancel, or later to switch back. The single-arrow Helsing switches at once, with the game's own reload.\n\nJAMMING\n\n<tab>Weapons in Metro Exodus can get jammed. Their condition affects how often that happens. To reduce the jamming rate, find a Workbench and clean your weapons. To unjam your weapon operate the bolt.\n\nAUTOMATIC RELOADS\n\n<tab>You can also disable manual reloads in Options - VR - Weapons and reload by pressing <rui> instead.",
        ru="РУЧНАЯ ПЕРЕЗАРЯДКА\n\n<tab>Для большинства оружий потребуется выполнять эти действия с помощью <trigger_nondominant>:\n\n* вынуть старый магазин\n* достать новый магазин из подсумка (<nondominant> бедро или грудь) и вставить его\n* при необходимости передернуть затвор\n\nУ некоторых оружий есть особые требования:\n\n* протолкнуть магазин через оружие, прежде чем его можно будет вынуть\n* потянуть рычаг, чтобы освободить магазин или дослать новый патрон\n* натянуть лук перед вставкой стрелы\n* накачать пневматическую систему (см. ниже)\n\n<tab>Если не знаете, что делать, включите ПОДСВЕТКУ ЧАСТЕЙ в Настройки – VR – Оружие. Она подсветит следующую часть, с которой нужно работать для перезарядки.\n\nПНЕВМАТИЧЕСКОЕ ОРУЖИЕ\n\n<tab>Тихару, Хельсингу и Гатлингу нужно давление. Качайте вручную <nondominant> рукой: возьмите рукоятку помпы с помощью <trigger_nondominant> и качайте вперед-назад; при полной накачке она отпустится сама. Либо удерживайте <rui> и нажимайте <wpn_fire>.\n\nОСОБЫЕ БОЕПРИПАСЫ\n\n<tab>Тихар может стрелять зажигательными боеприпасами, а Хельсинг – разрывными болтами. Держа оружие в руках, удерживайте <popup_equipment> и одновременно нажмите <rui>. Импульс подтвердит, что при следующей перезарядке зарядятся другие боеприпасы; перезаряжайтесь вручную как обычно. Повторите, чтобы отменить, или позже, чтобы переключиться обратно. Однострельный Хельсинг переключается сразу, при перезарядке самой игры.\n\nЗАКЛИНИВАНИЕ\n\n<tab>Оружие в Metro Exodus может заклинивать. Его состояние влияет на частоту заклиниваний. Чтобы снизить вероятность, найдите верстак и почистите оружие. Чтобы устранить заклинивание, передерните затвор.\n\nАВТОМАТИЧЕСКАЯ ПЕРЕЗАРЯДКА\n\n<tab>Также можно отключить ручную перезарядку в Настройки – VR – Оружие и перезаряжаться нажатием <rui>.",
    ),
    dict(
        index=5,
        orig_title="Items and devices",
        ru_title="ПРЕДМЕТЫ И УСТРОЙСТВА",
        orig="EQUIPPING GEAR\n\n<tab>Most of your gear is accessible directly from your body by moving your hand to a given area and gripping it with <grip_dominant> or <grip_nondominant>. Some gear can only be grabbed with a specific hand.\n\nGEAR AREAS\n\n* chest:\n  * <dominant> - map\n  * <nondominant> - lighter\n* shoulders:\n  * over <dominant> - main weapon (<grip_dominant>)\n  * over <nondominant> - special weapon (<grip_dominant>) or backpack (<grip_nondominant>)\n  * on <dominant> - medkit (<grip_nondominant>)\n* hips:\n  * <dominant> - secondary weapon (<grip_dominant>)\n  * <nondominant> - mask (<grip_nondominant>) or new ammo (<trigger_nondominant>)\n* lower back:\n  * <dominant> - charger (<grip_dominant>)\n  * <nondominant> - binoculars (<grip_nondominant>)\n* belt:\n  * front - throwables\n* forehead:\n  * flashlight (<trigger_nondominant>)\n  * night vision (<grip_dominant> - pull up or down)\n\n",
        ru="ЭКИПИРОВКА СНАРЯЖЕНИЯ\n\n<tab>Большинство снаряжения доступно прямо на теле: поднесите руку к нужной области и схватите предмет с помощью <grip_dominant> или <grip_nondominant>. Некоторое снаряжение можно взять только определенной рукой.\n\nЗОНЫ СНАРЯЖЕНИЯ\n\n* грудь:\n  * <dominant> – карта\n  * <nondominant> – зажигалка\n* плечи:\n  * из-за <dominant> – основное оружие (<grip_dominant>)\n  * из-за <nondominant> – особое оружие (<grip_dominant>) или рюкзак (<grip_nondominant>)\n  * на <dominant> – аптечка (<grip_nondominant>)\n* бедра:\n  * <dominant> – запасное оружие (<grip_dominant>)\n  * <nondominant> – маска (<grip_nondominant>) или новые боеприпасы (<trigger_nondominant>)\n* поясница:\n  * <dominant> – зарядное устройство (<grip_dominant>)\n  * <nondominant> – бинокль (<grip_nondominant>)\n* пояс:\n  * спереди – метательные предметы\n* лоб:\n  * фонарь (<trigger_nondominant>)\n  * ночное видение (<grip_dominant> – потяните вверх или вниз)\n\n",
    ),
    dict(
        index=6,
        orig_title="Gas mask",
        ru_title="ПРОТИВОГАЗ",
        orig="GAS MASK\n\n<tab>The gas mask is usually located on your <nondominant> hip. To put it on you have to grab it (<grip_nondominant>) and bring it to your face. To take it off you have to grab it from your face (<grip_nondominant>), move it away and let it go.\n\nFILTERS\n\n<tab>When the mask is equipped and your filters can be changed, a new filter will be available for grabbing (<grip_nondominant>) at your <nondominant> hip. Once grabbed, move it close to where it sits on the mask and it will be replaced automatically.[ Alternatively <press:filter>.]\n\nWIPING\n\n<tab>Rub the visor with an open hand to wipe rain, blood or dirt off it.[ Alternatively <press:facepalm>.]\n\nFIXING CRACKS\n\n<tab>When your mask is cracked, a piece of tape will be available for grabbing (<grip_nondominant>) at your <nondominant> hip, in place of the filter. Once grabbed, bring it to the front of your visor and the cracks will be sealed. Let go of it anywhere else to put it back.[ Alternatively <press:facepalm>.]\n\n",
        ru="ПРОТИВОГАЗ\n\n<tab>Противогаз обычно висит на <nondominant> бедре. Чтобы надеть его, схватите (<grip_nondominant>) и поднесите к лицу. Чтобы снять, схватите его на лице (<grip_nondominant>), отведите в сторону и отпустите.\n\nФИЛЬТРЫ\n\n<tab>Когда маска надета и фильтры можно менять, новый фильтр появится на <nondominant> бедре и его можно будет схватить (<grip_nondominant>). Схватив, поднесите его к месту установки на маске – он заменится автоматически.[ Либо <press:filter>.]\n\nПРОТИРАНИЕ\n\n<tab>Потрите стекло открытой ладонью, чтобы стереть дождь, кровь или грязь.[ Либо <press:facepalm>.]\n\nУСТРАНЕНИЕ ТРЕЩИН\n\n<tab>Когда маска треснула, на <nondominant> бедре появляется кусок скотча, который можно схватить (<grip_nondominant>) вместо фильтра. Схватив, поднесите его к передней части стекла, и трещины заделаются. Отпустите его в любом другом месте, чтобы вернуть.[ Либо <press:facepalm>.]\n\n",
    ),
    dict(
        index=7,
        orig_title="Medkit",
        ru_title="АПТЕЧКА",
        orig="HEALING\n\n<tab>When you're hurt you will hear specific audio cues and see a red overlay around your field of view. To heal yourself (assuming you have any medkits left):\n\n1. grip and hold (<grip_nondominant>) at your <dominant> shoulder\n2. move it away from your body until you feel a pulse\n3. bring it back to your body - anywhere from above your shoulder down to your stomach - to inject\n\n<tab>Letting go before that puts it back unused.[ Alternatively <press:medkit>.]\n\n",
        ru="ЛЕЧЕНИЕ\n\n<tab>Когда вы ранены, вы услышите характерные звуки и увидите красную рамку по краям обзора. Чтобы вылечиться (если остались аптечки):\n\n1. схватите и удерживайте (<grip_nondominant>) у <dominant> плеча\n2. отведите от тела, пока не почувствуете импульс\n3. верните к телу – от уровня выше плеча до живота – чтобы сделать укол\n\n<tab>Если отпустить раньше, аптечка вернется неиспользованной.[ Либо <press:medkit>.]\n\n",
    ),
    dict(
        index=8,
        orig_title="Flashlight and charger",
        ru_title="ФОНАРЬ И ЗАРЯДКА",
        orig="FLASHLIGHT\n\n<tab>To toggle the flashlight, press <trigger_nondominant> at your forehead[, or <press:wpn_light>].\n\nCHARGER\n\n<tab>To charge your batteries, grip (<grip_dominant>) at the <dominant> side of your lower back[, or <press:charger>]. Once equipped, pump it with <wpn_fire>.\n\n",
        ru="ФОНАРЬ\n\n<tab>Чтобы включить или выключить фонарь, нажмите <trigger_nondominant> у лба[, или <press:wpn_light>].\n\nЗАРЯДНОЕ УСТРОЙСТВО\n\n<tab>Чтобы зарядить аккумуляторы, схватите (<grip_dominant>) устройство с <dominant> стороны поясницы[, или <press:charger>]. Взяв его, качайте с помощью <wpn_fire>.\n\n",
    ),
    dict(
        index=9,
        orig_title="Map / journal",
        ru_title="КАРТА И ЖУРНАЛ",
        orig="MAP\n\n<tab>To equip the map, simply grip it (<grip_dominant>) at the <dominant> side of your chest[, or <press:map>].\n\nJOURNAL\n\n<tab>Once the map is equipped, flip the map over with your hands, or press <wpn_fire> to switch sides.\n\n",
        ru="КАРТА\n\n<tab>Чтобы взять карту, просто схватите ее (<grip_dominant>) у <dominant> стороны груди[, или <press:map>].\n\nЖУРНАЛ\n\n<tab>Взяв карту, переверните ее руками или нажмите <wpn_fire>, чтобы сменить сторону.\n\n",
    ),
    dict(
        index=10,
        orig_title="Backpack / inventory",
        ru_title="РЮКЗАК И ИНВЕНТАРЬ",
        orig="OPENING BACKPACK\n\n<tab>To open your inventory, grip (<grip_nondominant>) over your <nondominant> shoulder[, or <press:inventory>]. Once opened you can craft consumables/throwables and modify your weapons. Standard UI navigation rules apply - either use your controller's pointer and triggers or point away and press buttons as shown on screen.\n\n",
        ru="ОТКРЫТИЕ РЮКЗАКА\n\n<tab>Чтобы открыть инвентарь, схватите (<grip_nondominant>) над <nondominant> плечом[, или <press:inventory>]. В нем можно создавать расходники и метательные предметы, а также улучшать оружие. Действуют обычные правила навигации: используйте указатель контроллера и триггеры либо отведите взгляд и нажимайте кнопки, показанные на экране.\n\n",
    ),
    dict(
        index=11,
        orig_title="Binoculars and NV",
        ru_title="БИНОКЛЬ И НОЧНОЕ ВИДЕНИЕ",
        orig="BINOCULARS\n\n<tab>Once you have binoculars, grip (<grip_nondominant>) at the <nondominant> side of your lower back[, or <press:binoculars>]. You can pass them between hands. To use them, bring them to your eyes. Zoom in with <wpn_fire> and out with <aim>.\n\nNIGHT VISION\n\n<tab>To equip night vision, grip (<grip_dominant>) above your forehead and pull them down in front of your eyes[, or <press:nightvision>]. To take them off, grip (<grip_dominant>) in front of your eyes and pull them back up[, or <press:nightvision> again].\n\n",
        ru="БИНОКЛЬ\n\n<tab>Получив бинокль, схватите (<grip_nondominant>) его с <nondominant> стороны поясницы[, или <press:binoculars>]. Его можно передавать между руками. Чтобы использовать, поднесите к глазам. Приближайте с помощью <wpn_fire>, отдаляйте с помощью <aim>.\n\nНОЧНОЕ ВИДЕНИЕ\n\n<tab>Чтобы надеть ночное видение, схватите (<grip_dominant>) над лбом и потяните вниз перед глазами[, или <press:nightvision>]. Чтобы снять, схватите (<grip_dominant>) перед глазами и потяните вверх[, или снова <press:nightvision>].\n\n",
    ),
    dict(
        index=12,
        orig_title="Weapon scopes",
        ru_title="ОРУЖЕЙНЫЕ ПРИЦЕЛЫ",
        orig="<tab>To use weapon scopes simply bring them to your eye. You can configure related options in Options - VR - Scopes.\n\n",
        ru="<tab>Чтобы использовать прицел, просто поднесите его к глазу. Связанные настройки – в Настройки – VR – Прицелы.\n\n",
    ),
    dict(
        index=13,
        orig_title="Workbenches",
        ru_title="ВЕРСТАКИ",
        orig="<tab>To use a workbench, reach out to it and grip (<grip_dominant> or <grip_nondominant>). Once in the workbench view use your controller's pointer and triggers or the buttons shown on screen to navigate the view.\n\n",
        ru="<tab>Чтобы воспользоваться верстаком, потянитесь к нему и схватите (<grip_dominant> или <grip_nondominant>). В режиме верстака используйте указатель контроллера и триггеры либо кнопки на экране для навигации.\n\n",
    ),
]

doc["hintpages"] = pages
path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("added", len(pages), "hint pages")
