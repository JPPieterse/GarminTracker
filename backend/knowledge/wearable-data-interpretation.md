# Wearable Data Interpretation

> Module for ZEV AI coaching knowledge base

## Garmin Body Battery

Body Battery is a 0-100 score that estimates your body's energy reserves throughout the day. It's powered by Firstbeat Analytics (acquired by Garmin in 2020) and draws on heart rate variability (HRV), stress levels, sleep quality, and physical activity.

**How to read it:**
- **75-100:** High energy reserves. Good time for hard training sessions.
- **50-75:** Moderate energy. Fine for easy training, but maybe not the day for your hardest workout.
- **25-50:** Low energy. Prioritize recovery, easy movement, or rest.
- **0-25:** Depleted. Rest is your best training decision today.

**How to use it for training decisions:**
- Check Body Battery in the morning before deciding workout intensity
- If Body Battery didn't recharge well overnight (didn't recover above 70-80), something disrupted your recovery — poor sleep, alcohol, illness, or accumulated training stress
- Watch the trend over a week, not just one day. A pattern of declining overnight recovery signals you need to back off
- Body Battery drops during activity and stress and recharges during rest and sleep. A big overnight recharge (40+ points) suggests quality recovery

**Limitations:** Body Battery is a broad indicator, not a precise medical tool. Caffeine, medications, and individual HRV patterns can affect accuracy. Use it as one input alongside how you actually feel.

## Stress Score

Garmin's stress score (0-100) measures autonomic nervous system load derived from heart rate variability patterns. It does not directly measure cortisol, emotional stress, anxiety, or mental health.

**How to interpret it:**
- **0-25:** Resting state. Low physiological stress.
- **26-50:** Low stress. Normal daily activity.
- **51-75:** Medium stress. Elevated sympathetic nervous system activity.
- **76-100:** High stress. Significant physiological load.

**What drives it up:** Physical exercise, caffeine, alcohol, poor sleep, illness, dehydration, emotional stress, and even digestion after large meals.

**When to pay attention:** Look at your stress score during periods you expect to be calm (sitting at a desk, sleeping). If your "resting" stress is consistently elevated above your personal norm, consider whether you're overtraining, under-sleeping, or dealing with other recovery-limiting factors.

**Key limitation:** Intense exercise registers as high stress on the score, which is expected and not a concern. The score is most useful for understanding your recovery state outside of workouts.

## VO2 Max Estimate

Garmin estimates your VO2 max using pace-to-heart-rate relationships during outdoor runs and cycling. Under controlled conditions with a chest strap, the estimate is typically within 5% of lab-tested values. With wrist-based heart rate, accuracy decreases.

**Accuracy factors:**
- For moderately trained athletes (VO2 max below 60 ml/kg/min), Garmin is often within 2-3% of lab values
- For highly trained athletes, Garmin tends to underestimate by about 10%
- Wrist-based HR can underread heart rate, which inflates the VO2 max estimate
- Heat, hills, wind, and trail surfaces all affect the calculation
- The estimate needs several weeks of data before it stabilizes

**What affects your VO2 max number:**
- Consistent training improves it (especially zone 2 volume and high-intensity intervals)
- Overtraining, illness, and poor recovery can temporarily lower it
- Running on soft surfaces, trails, or in heat may produce lower readings (more effort for the same pace)
- Significant weight change affects the relative (per kg) calculation

**How to improve it:** Build aerobic base with zone 2 training, add 1-2 high-intensity interval sessions per week, maintain consistency over months, and ensure adequate recovery.

## Training Load and Training Status

**Training Load** quantifies the total stress from your recent training using exercise post-oxygen consumption (EPOC) values. Garmin tracks this over 7-day and 4-week windows.

**Training Status** combines your recent training load trend with your VO2 max trend to produce an assessment:

- **Peaking:** Training load is decreasing while fitness is at its highest. Ideal for race day.
- **Productive:** Current training is improving fitness. Keep doing what you're doing.
- **Maintaining:** Fitness is steady. Fine if you're in a maintenance phase, but increase load if you want to improve.
- **Recovery:** Light training load is allowing your body to recover. Normal after hard training blocks.
- **Unproductive:** Training load is high but fitness isn't improving. Could indicate insufficient recovery, illness, or inappropriate intensity distribution.
- **Detraining:** Training load has dropped enough that fitness is declining. Time to get back to consistent training.
- **Overreaching:** Very high training load with declining performance. Back off before this becomes overtraining.

**Practical use:** If your status reads "Unproductive" for more than a week, don't train harder — train smarter. Often the fix is more easy volume and better recovery, not more intensity.

## Sleep Tracking

Garmin tracks total sleep time, sleep stages (light, deep, REM, awake), and generates a sleep score. Total sleep time is generally accurate. Sleep stage identification is less reliable.

**What wearables get right:**
- Total time asleep (usually within 15-30 minutes of actual)
- General sleep quality trends over weeks and months
- Detecting significantly disrupted nights

**What wearables get wrong:**
- Precise sleep stage classification (accuracy around 40-50% for stage identification in some studies, though recent Garmin models have improved)
- Brief awakenings are often missed or misclassified
- Nap detection can be inconsistent

**How to use sleep data:**
- Track your sleep score trend over 2-4 weeks rather than obsessing over a single night
- Prioritize total sleep time — most athletes need 7-9 hours
- If your sleep score drops consistently, investigate the cause: stress, late caffeine, screen time, inconsistent schedule
- Deep sleep percentage is linked to physical recovery; REM to cognitive recovery and learning

## Steps as a Health Metric

The 10,000-step target is not scientifically derived — it originated from a 1960s Japanese marketing campaign for a pedometer. However, research consistently shows that more daily movement is better for health outcomes.

**What the evidence says:**
- Health benefits increase significantly from sedentary (under 4,000 steps) up to about 7,500-8,000 steps daily
- Benefits continue beyond 10,000 steps but with diminishing returns
- For older adults, even 4,400 steps daily is associated with reduced mortality compared to 2,700 steps
- The type of movement matters too — a 30-minute walk provides different benefits than 30 minutes of accumulated fidgeting

**Practical guidance:** Aim for 7,000-10,000 steps as a baseline, with the understanding that this is a proxy for general daily movement. For athletes who train regularly, step count is less important than overall training structure, but non-exercise movement still matters for health.

## SpO2 (Blood Oxygen Saturation)

SpO2 measures the percentage of hemoglobin in your blood that is carrying oxygen.

**Normal ranges:**
- **95-100%:** Normal for healthy individuals
- **90-94%:** Mildly low — worth monitoring, could indicate altitude, respiratory issues, or sensor error
- **Below 90%:** Clinically significant — seek medical attention if this is a consistent reading, not a momentary sensor glitch

**When to pay attention:**
- Consistently low overnight SpO2 readings may warrant a conversation with a doctor about sleep apnea or respiratory health
- Altitude will naturally lower SpO2 — this is expected at elevation
- Single low readings on a wrist sensor are often noise. Look for patterns across multiple nights
- SpO2 from a wrist wearable is less accurate than a medical pulse oximeter, especially at lower saturation levels

**For athletes:** SpO2 data is most useful for detecting sleep apnea patterns or monitoring acclimatization at altitude. For everyday training at sea level, it's generally less actionable than heart rate and HRV data.

## Intensity Minutes

Garmin's Intensity Minutes track time spent in moderate-to-vigorous physical activity, aligning with WHO guidelines recommending 150 minutes of moderate or 75 minutes of vigorous activity per week.

**How it works:**
- Moderate intensity minutes are earned in heart rate zone 3 and above (or through elevated step cadence)
- Vigorous intensity minutes count double (1 minute of vigorous activity = 2 intensity minutes)
- The weekly goal defaults to 150 minutes

**Practical use:** This metric is most valuable for people who aren't following structured training plans. If you're already tracking your running, cycling, and gym sessions, intensity minutes don't add much new information. They're a solid motivational tool for ensuring you're meeting minimum activity guidelines.

## When to Trust Your Body Over the Watch

Wearable data is powerful, but it's a tool, not an authority. Here's when to override the numbers:

**Trust your body when:**
- The watch says you're recovered but you feel exhausted, sore, or mentally drained
- Your heart rate seems normal but your legs feel dead — accumulated muscular fatigue doesn't always show in HR data
- You feel great but the watch says your Training Status is "Unproductive" — sometimes the algorithm needs time to catch up
- You're sick — no metric should convince you to train hard when you're ill

**Trust the data when:**
- You feel fine but your resting heart rate has been elevated for several days — early overtraining often feels invisible
- You want to push harder but Body Battery shows consistently poor recovery
- You think your easy runs are easy but heart rate data shows you're spending too much time in zone 3-4
- You believe you're sleeping well but your sleep data shows 5.5 hours of actual sleep

The best approach is treating wearable data as a second opinion, not the final word. When your subjective feel and objective data agree, you have high confidence. When they disagree, investigate rather than blindly following either one.
