import sqlite3
import os

DATABASE = 'medicare.db'

# Extensive list of common medicines (Brand + Generic + Uses + Interactions)
medicines_data = [
    # --- PAIN & FEVER ---
    ("dolo", "paracetamol", "Used for fever and mild pain.", "alcohol, warfarin, liver disease"),
    ("crocin", "paracetamol", "Common fever reducer and pain reliever.", "alcohol, warfarin"),
    ("calpol", "paracetamol", "Pediatric and adult fever reducer.", "alcohol, overdose"),
    ("combiflam", "ibuprofen + paracetamol", "Strong pain killer for body ache.", "aspirin, alcohol, kidney issues"),
    ("meftal spas", "mefenamic acid", "Used for menstrual cramps and stomach pain.", "blood thinners, alcohol"),
    ("disprin", "aspirin", "Headache relief and blood thinner.", "ibuprofen, warfarin, bleeding disorders"),
    ("ecosprin", "aspirin", "Prevents blood clots/heart attacks.", "ibuprofen, warfarin"),
    ("brufen", "ibuprofen", "Anti-inflammatory for joint pain.", "aspirin, heart meds"),
    ("volini", "diclofenac", "Spray/Gel for muscle sprains and joint pain.", "open wounds, asthma"),
    ("zerodol", "aceclofenac", "For arthritis and severe inflammation.", "alcohol, kidney disease"),
    ("ultracet", "tramadol + paracetamol", "For severe pain (requires prescription).", "alcohol, sleeping pills, antidepressants"),

    # --- ANTIBIOTICS (Infection) ---
    ("augmentin", "amoxiclav", "Broad spectrum antibiotic for bacterial infections.", "birth control pills, gout meds"),
    ("azithral", "azithromycin", "Throat and chest infections (3-5 day course).", "antacids, heart meds"),
    ("ciplox", "ciprofloxacin", "For urinary tract and stomach infections.", "dairy, calcium, theophylline"),
    ("taxim-o", "cefixime", "Antibiotic for ear, throat, and urinary infections.", "blood thinners"),
    ("doxy-1", "doxycycline", "For acne and bacterial infections.", "milk, iron supplements, sun exposure"),
    ("flagyl", "metronidazole", "For diarrhea and stomach infections.", "alcohol (severe reaction)"),
    
    # --- ACIDITY & GASTRIC ---
    ("pan 40", "pantoprazole", "Empty stomach pill for acidity and GERD.", "clopidogrel, iron supplements"),
    ("pan d", "pantoprazole + domperidone", "Acidity with nausea/vomiting.", "heart meds, antibiotics"),
    ("omez", "omeprazole", "Relief from heartburn and ulcers.", "clopidogrel, antifungal meds"),
    ("rantac", "ranitidine", "Older acidity medication (check availability).", "alcohol"),
    ("digene", "antacid", "Pink liquid/tablet for instant acidity relief.", "antibiotics (space by 2 hours)"),
    ("gelusil", "antacid", "Minty syrup for heartburn.", "tetracycline, iron"),
    ("eno", "sodium bicarbonate", "Instant gas relief powder.", "high blood pressure"),

    # --- COLD, COUGH & ALLERGY ---
    ("allegra", "fexofenadine", "Non-drowsy allergy relief.", "fruit juice (orange/apple)"),
    ("cetzine", "cetirizine", "For runny nose and itching (causes drowsiness).", "alcohol, driving"),
    ("levocet", "levocetirizine", "Advanced allergy relief.", "alcohol, sedatives"),
    ("montair-lc", "montelukast + levocetirizine", "For asthma and allergic rhinitis.", "aspirin"),
    ("benadryl", "diphenhydramine", "Cough syrup and allergic reaction relief.", "alcohol, sleeping pills"),
    ("ascoril", "terbutaline + bromhexine", "Expectorant for wet cough.", "heart rate meds"),
    ("alex", "dextromethorphan", "Syrup for dry cough.", "antidepressants (MAOIs)"),
    ("wikoryl", "phenylephrine + paracetamol", "Total relief for cold, fever, blocked nose.", "alcohol, high bp"),
    ("otrivin", "xylometazoline", "Nasal spray for blocked nose.", "do not use >5 days"),

    # --- CHRONIC (Diabetes, BP, Thyroid) ---
    ("glycomet", "metformin", "First-line diabetes medicine.", "alcohol, kidney contrast dye"),
    ("januvia", "sitagliptin", "For type 2 diabetes sugar control.", "insulin"),
    ("amlosafe", "amlodipine", "For high blood pressure.", "grapefruit"),
    ("telma", "telmisartan", "BP medicine, kidney protection.", "potassium supplements"),
    ("atorva", "atorvastatin", "Cholesterol lowering medicine.", "grapefruit, alcohol"),
    ("thyronorm", "levothyroxine", "Thyroid hormone replacement (empty stomach).", "calcium, iron, soy"),
    
    # --- VITAMINS & SUPPLEMENTS ---
    ("limcee", "vitamin c", "Chewable immunity booster.", "none"),
    ("becosules", "b-complex", "For mouth ulcers and energy.", "levodopa"),
    ("shelcal", "calcium + vitamin d3", "Bone strength.", "iron, thyroid meds, antibiotics"),
    ("zincovit", "multivitamin + zinc", "General immunity and weakness.", "antibiotics"),
    ("neurobion", "vitamin b12", "For nerve health and tingling.", "alcohol"),
    ("evion", "vitamin e", "For skin and hair health.", "blood thinners"),

    # --- OTHERS ---
    ("viagra", "sildenafil", "For erectile dysfunction.", "nitrates, heart meds, nitroglycerin"),
    ("manforce", "sildenafil", "For erectile dysfunction.", "nitrates, heart meds"),
    ("ipill", "levonorgestrel", "Emergency contraceptive (72 hours).", "barbiturates"),
    ("betadine", "povidone iodine", "Antiseptic for cuts and wounds.", "burns"),
]

def force_feed():
    print(f"📂 connecting to database: {DATABASE}")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # 1. Ensure Table Exists
    c.execute('''CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,       
            generic_name TEXT,               
            description TEXT,
            interactions TEXT                
        )''')
    
    # 2. CLEAR OLD DATA (To ensure no duplicates or stale data)
    print("🧹 Clearing old medicine data...")
    c.execute("DELETE FROM medicines")
    conn.commit()

    # 3. INSERT NEW DATA
    print("🚀 Inserting new medicines...")
    count = 0
    for name, generic, desc, interact in medicines_data:
        try:
            c.execute("""
                INSERT INTO medicines (name, generic_name, description, interactions) 
                VALUES (?, ?, ?, ?)
            """, (name, generic, desc, interact))
            count += 1
        except Exception as e:
            print(f"❌ Error adding {name}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ SUCCESS! Added {count} medicines to database.")
    print("👉 NOW: Restart your Flask server (Ctrl+C and python app.py) to see changes.")

if __name__ == "__main__":
    force_feed()