[English version](#en)
## **РУ**
Мод добавляет озвучку ГГ голосами из EFT в зависимости от условий. В качестве кодовой базы использован мод [Voiced Actor Expanded 2.1](https://www.moddb.com/mods/stalker-anomaly/addons/voiced-actor-expanded) за авторством [LuxoSVK](https://www.moddb.com/members/luxosvk).
Использованы наработки других авторов: Ayykyu , Grokitach, Dhatri и других авторов сообщества STALKER ANOMALY (если увидели свою разработку в коде мода и я не упомянул вас - просьба написать мне в Дискорд werwolf969 и я исправлю это недоразумение. Мод рассчитан на работу со сборкой GAMMA.

**Новое по сравнению с Voiced Actor Expanded 2.1:**
Все файлы озвучки были нормализованы по уровню громкости в соответствии со стандартами, чтобы не вызывать дискомфорта при прослушивании.  Больше никаких резких выкриков выше громкости игры. 
Озвучка звуков при надетой маске/шлеме полностью переделана, чтобы передать эффект слышимости звуков изнутри маски, а не как нас слышал бы собеседник. Добавлены звуки при надетом маске/шлеме для всех файлов озвучки для обоих языков озвучки.
Изменена структура мода, изменения функций напарников вынесены за пределы axr_companions для лучшей совместимости.
Нативно поддерживается озвучка Doom like Weapons Inspections и BHS, меню напарников, BHSRO поддерживается через патч совместимости.
Добавлено MCM меню (VARefined) для тонкой настройки мода, возможности настройки:
- Регулировка громкости озвучки
- Выбор языка озвучки критериям: по-умолчанию для GAMMA (английская для ISG и Наемников, русская для всех остальных), только русская, только английская.
- Включение/выключение озвучки убийств.
- Включение/выключение озвучки клина оружия (при наличии WPO автоматически отключит озвучку клина в нем для избежания дублирования).
- Включение/выключение озвучки при перезарядке оружия.
- Включение/выключение озвучки при бросках гранат.
- Включение/выключение озвучки команд напарникам при наличии напарников.
- Включение/выключение озвучки боли ГГ из этого мода. Отключение опции поможет в случае, если вам кажется что персонаж издает слишком часто звуки при потере здоровья с включенным BHS/BHSRO.

- Включение/выключение "приглушенной" озвучки при надетой маске/шлеме.
- Клавиша ситуативных комментариев ГГ.
- Клавиша случайных выкриков ГГ.

Изменены веса для вероятности озвучки убийств, теперь они будут происходить реже.
Вся озвучка учитывает условия ГГ:
- ГГ один/в скваде, 
- ГГ в бою недавно/среднее время/длительное время,
- сквад близко/на средней дистанции/ далеко от ГГ,
- ГГ здоров/ранен/сильно ранен,
- уровень жажды/сонливости/пси здоровья/выносливости.

## **EN**
The mod adds Actor voice lines with voices from EFT, depending on the conditions. The mod [Voiced Actor Expanded 2.1](https://www.moddb.com/mods/stalker-anomaly/addons/voiced-actor-expanded) is used as the codebase authored by [LuxoSVK](https://www.moddb.com/members/luxosvk).
Other authors developments were used: Ayykyu, Grokitach, Dhatri and other authors of the STALKER ANOMALY community (if you saw your development in the mod code and I didn't mention you, please write to me in Discord werwolf969 and I will correct this misunderstanding. The mod made with GAMMA modpack in mind.

**New compared to Voiced Actor Expanded 2.1:**
All voice files have been normalized by loudness level in accordance with the standards, so as not to cause any discomfort when listening. No more harsh shouting above the game volume. 
The sounds when wearing a mask / helmet has been completely redesigned to convey the effect of hearing sounds from inside the mask, and not as the interlocutor would hear us. Added sounds when wearing a mask/helmet for all voice files for both voiced languages.
The mod structure has been changed, and changes to partner functions have been moved beyond axr_companions for better compatibility.
Natively supported voice acting of Doom like Weapons Inspections and BHS, companions menu, BHSRO is supported through the compatibility patch.
Added MCM menu (VARefined) for fine-tuning the mod, customization options:
- Adjust the voice output volume
- Select the voice language.: by default for GAMMA (English for ISG and Mercenaries, Russian for everyone else), Russian only, English only.
- Enable / disable voice-over of kills.
- Enable / disable weapon jam voiceover (if available, inside WPO will be automatically disabled the jam voiceover to avoid duplication).
- Enable / disable voice lines when reloading weapons.
- Enable / disable voice lines when throwing grenades.
- Enable / disable voice lines for companion commands if there are companions.
- Enable / disable voice lines for Actor in pain from this mod. Disabling this option will help if you think that the actor makes too many sounds when losing health with BHS/BHSRO enabled.

- Enable / disable "muffled" sounds when wearing a mask / helmet.
- Situational comments key voice lines.
- Random Actor shouting key voice lines.

Changed the weights for the probability of playing voice lines for kills, now they will occur less frequently.
All voice lines takes into account Actor conditions:
- actor alone/in squad, 
- actor in combat recently/average time/long time,
- squad close/medium distance/ far from actor,
- actor is healthy/injured/badly injured,
- thirst/sleepiness/psy health/stamina level of actor.

## **Implemented reactions:**
<voice lines start here>

| Parent folder | Folder | Description |
|---|---|---|
