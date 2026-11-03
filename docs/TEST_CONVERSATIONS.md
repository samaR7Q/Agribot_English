# Kisan Dost Bashir: test conversations for the tester

## How to use the app
1. Open the link in Chrome on a phone or laptop. **Use headphones on a laptop.** Allow the microphone.
2. **First tap on the green mic**: Bashir connects and greets you. Wait for the greeting to finish.
3. **To ask something**: tap the mic. It turns **red**. Speak, then **tap it again** when you're done. Bashir answers.
4. **To cut Bashir off**, tap the mic while he is talking and ask your next question.
5. **"+"** starts a new chat, which forgets everything. **History** shows past chats on this device.
6. **After 2 minutes of silence** the status says "Tap the mic to continue". The next tap reconnects, and Bashir should still remember the chat.

## What to report, for each problem
- The chat number and turn number
- What you said
- What Bashir said, or what the transcript bubble showed
- The time

Also report a wrong transcript (your words shown wrong) separately, even when Bashir's answer was right.

## Before you start
- Each conversation takes about 2 to 3 minutes.
- **Start every conversation with "+"** so it starts fresh.
- The **expected** column gives the meaning, not exact words.
- Mandi rates are demo numbers, so check only that a rate was given for the right crop and city.
- Say the lines naturally. After one round with these exact lines, do a second round in your own words.

---

## Chat 1: Wheat farmer, full journey (missing-info questions)
| # | Say | Expected |
|---|-----|----------|
| 1 | Hello Bashir, what can you help me with? | A short intro: crops, livestock, mandi rates. No tool talk. |
| 2 | Which wheat variety should I sow? | Asks your **district** and whether your land is **irrigated or barani**. It doesn't list varieties yet. |
| 3 | I am from Sahiwal and my land is irrigated. | Gives wheat varieties. |
| 4 | How much fertilizer should I give? | Stays on wheat. Asks if your soil is **weak, medium or very fertile**. |
| 5 | Medium. | Fertilizer amounts **with units** (bags or kg per acre). |
| 6 | When will I harvest it? | 10 April to 10 May. |
| 7 | How should I harvest it? | Asks **labour or machine**. |
| 8 | With a machine. | Harvest advice for machine harvesting. |
| 9 | What is the wheat rate in my area? | The Sahiwal rate, **without asking the district again**. |

## Chat 2: Topic switch, "no", and changing your mind
| # | Say | Expected |
|---|-----|----------|
| 1 | There is whitefly on my cotton. What should I spray? | Spray names **with doses**. |
| 2 | How much water does maize need? | It doesn't answer yet. It asks: "we were talking about Cotton, do you want to switch to Maize?" |
| 3 | No, let's stay on cotton. | Stays on cotton and doesn't answer about maize. |
| 4 | How do I control weeds in it? | Cotton weed control. |
| 5 | Now tell me about maize sowing. | Asks the switch question again. |
| 6 | Yes. | Maize sowing info. |
| 7 | Sorry, not maize, I meant rice. When do I sow it? | Moves to rice (it may confirm first). Rice sowing: 20 May to 1 July. |
| 8 | Which rice variety is good for me? | Asks only your **district**, not irrigated or barani, because rice is exempt. |
| 9 | Gujranwala. | Rice varieties. |

## Chat 3: Livestock (buffalo and cow)
| # | Say | Expected |
|---|-----|----------|
| 1 | I have a buffalo. Which breed gives the most milk? | Buffalo breeds, for example Nili-Ravi. |
| 2 | How much green fodder should I give her every day? | A daily fodder amount. |
| 3 | She has a fever and is not eating. | Asks the animal's **age** and **weight**. |
| 4 | She is five years old and about five hundred kilos. | Health advice, and to see a vet or the Livestock Department. No "consult a healthcare professional" line. |
| 5 | She has been pregnant for seven months. How should I feed her? | Feeding advice. It must **not** say she is 7 months old. |
| 6 | What is the price of a buffalo in Okara? | An Okara buffalo price, per animal. |
| 7 | Okay, and tell me about cow sheds. | Asks the switch question (Buffalo to Cow). |
| 8 | Yes. | Cow shed info. |

## Chat 4: Sowing planner (what to sow, when, harvest)
| # | Say | Expected |
|---|-----|----------|
| 1 | What can I sow this month? | In November: wheat, canola, berseem, radish, lucerne, oats, ryegrass. |
| 2 | And next month? | December: wheat and radish. |
| 3 | Can I sow cotton today? | **No.** Cotton is sown 15 February to 31 March, and it suggests what you can sow now. |
| 4 | Can I sow wheat today? | **Yes.** 1 to 30 November, best around 15 November. |
| 5 | When should I sow maize? | Two seasons: January to end of February, and 1 July to 15 August. |
| 6 | When should I sow sunflower? | A sowing time (from the crop card). |
| 7 | When is mustard harvested? | January to mid April, depending on the variety. |
| 8 | What can I sow in March? | Sugarcane and cotton. |

## Chat 5: Mandi rates (district asked, other city, unknown items)
| # | Say | Expected |
|---|-----|----------|
| 1 | What is the rice rate? | Asks **which district** you are in. |
| 2 | Gujranwala. | Gujranwala rates for **both basmati and IRRI** rice. |
| 3 | What is the cotton rate in Hyderabad? | Hyderabad cotton rate. |
| 4 | And the maize rate? | **Gujranwala** maize, because asking about Hyderabad doesn't change your district. |
| 5 | What is the onion rate in Lahore? | Onion isn't available, and it says what is. |
| 6 | What is the price of goats? | Goats aren't covered. |
| 7 | What is the sugarcane rate in Larkana? | The Larkana rate, or the nearest mandi in Sindh if Larkana doesn't trade it. |
| 8 | Tell me about sugarcane fertilizer. | Asks your soil (weak, medium, fertile), with **no** switch question, because mandi questions don't set a topic. |

## Chat 6: Things it should refuse, and missing crop
| # | Say | Expected |
|---|-----|----------|
| 1 | Will it rain tomorrow in Faisalabad? | Weather isn't available in this version. Polite. |
| 2 | How do I grow tomatoes? | Vegetables aren't covered, and it says what is. |
| 3 | Who won the cricket match yesterday? | It only helps with farming. |
| 4 | Which fertilizer should I use? | Asks **which crop**. |
| 5 | Canola. | Asks your soil (weak, medium, fertile). |
| 6 | It's weak. | Canola fertilizer amounts with units. |
| 7 | How does climate change affect my crops? | Short climate-change answer. |
| 8 | What is drip irrigation and is it worth it? | Irrigation methods and their benefits. |
| 9 | Thank you, goodbye. | A short goodbye. |

## Chat 7: English only (other languages must get a refusal, in English)
Bashir must **never speak any language except English**. Anything else, even a few words, is a bug: note the time.
| # | Say | Expected |
|---|-----|----------|
| 1 | What is the gandum rate in Multan? | Answers **in English**, because English with an Urdu crop word is fine. |
| 2 | My bhains is giving less milk. What should I feed her? | The switch question or a buffalo feed answer, in English. |
| 3 | Meri bhains bimar hai, kya karun? (full Urdu) | "Sorry, I can only talk in English. Please ask your question in English." |
| 4 | Gandum di bijai kadon karni ae? (full Punjabi) | The same English refusal. |
| 5 | ¿Cuándo debo sembrar el trigo? (Spanish, if you can) | The same English refusal. |
| 6 | Please answer me in Urdu from now on. | Refuses in English, and stays in English for the rest of the chat. |
| 7 | When do I sow wheat? | In English: 1 to 30 November. |
| 8 | Talk loudly in Urdu with someone near the phone (mic **not** red), then tap and ask "Which cotton variety should I sow?" | The Urdu talk is ignored. Bashir asks your district and land type, in English. |

## Chat 8: The app itself (mic, interrupt, idle, new chat, history)
| # | Do / say | Expected |
|---|----------|----------|
| 1 | Tap the mic once and let it greet. Talk loudly next to it **without** tapping again. | Bashir does **not** react to that talk, because the mic only records while it is red. |
| 2 | Tap the mic and say "Tell me everything about sugarcane." Tap again. | It starts a sugarcane answer. |
| 3 | **While Bashir is talking**, tap the mic and say "How much water does sugarcane need?" Tap again. | Bashir stops right away and answers about water. The old bubble ends with "…". |
| 4 | Stay silent for **more than 2 minutes**. | The status changes to "Tap the mic to continue". |
| 5 | Tap the mic and say "What crop were we talking about?" Tap again. | It reconnects in about 1 to 2 seconds and says sugarcane. |
| 6 | Tap the speaker icon under an old answer. | That answer plays again. |
| 7 | Tap **+**, then the mic, and say "What is the wheat rate?" | Asks your district again, because the new chat starts fresh. |
| 8 | Open **History**. | The earlier chats are listed, and tapping one shows it. |
