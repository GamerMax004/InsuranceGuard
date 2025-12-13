import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta
import logging
import random
import string

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('insurance_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('InsuranceBot')

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Datenspeicherung
DATA_FILE = "insurance_data.json"
CONFIG_FILE = "bot_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"log_channel_id": None, "company_account_id": None}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

config = load_config()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            logger.info("Daten erfolgreich geladen")
            return json.load(f)
    logger.warning("Keine Datendatei gefunden, erstelle neue Datenstruktur")
    return {"customers": {}, "invoices": {}, "logs": []}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info("Daten erfolgreich gespeichert")

def generate_customer_id():
    """Generiert eine komplexe Kunden-ID"""
    prefix = "VN"
    year = datetime.now().strftime("%y")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}-{year}{random_part}"

def generate_invoice_id():
    """Generiert eine komplexe Rechnungs-ID"""
    prefix = "RE"
    year = datetime.now().strftime("%y")
    month = datetime.now().strftime("%m")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{year}{month}-{random_part}"

async def send_to_log_channel(guild, embed):
    """Sendet eine Nachricht in den Log-Channel"""
    if config["log_channel_id"]:
        try:
            log_channel = guild.get_channel(config["log_channel_id"])
            if log_channel:
                await log_channel.send(embed=embed)
                logger.info(f"Log an Channel {config['log_channel_id']} gesendet")
        except Exception as e:
            logger.error(f"Fehler beim Senden an Log-Channel: {e}")

def add_log_entry(action, user_id, details):
    """Fügt einen Log-Eintrag hinzu"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "user_id": user_id,
        "details": details
    }
    data['logs'].append(log_entry)
    save_data(data)
    logger.info(f"Log erstellt: {action} von User {user_id}")

data = load_data()

# Versicherungstypen mit Preisen und zugehörigen Rollen
INSURANCE_TYPES = {
    "Krankenversicherung (Gesetzlich)": {"price": 350.00, "role": "Krankenversicherung"},
    "Krankenversicherung (Privat)": {"price": 750.00, "role": "Krankenversicherung"},
    "Haftpflichtversicherung": {"price": 120.00, "role": "Haftpflichtversicherung"},
    "Hausratversicherung": {"price": 180.00, "role": "Hausratversicherung"},
    "Kfz-Versicherung": {"price": 500.00, "role": "Kfz-Versicherung"},
    "Rechtsschutzversicherung": {"price": 280.00, "role": "Rechtsschutzversicherung"},
    "Unfallversicherung": {"price": 220.00, "role": "Unfallversicherung"},
    "Berufsunfähigkeitsversicherung": {"price": 450.00, "role": "Berufsunfähigkeitsversicherung"}
}

# Farbschema
COLOR_PRIMARY = 0x2C3E50
COLOR_SUCCESS = 0x27AE60
COLOR_WARNING = 0xE67E22
COLOR_ERROR = 0xC0392B
COLOR_INFO = 0x3498DB

@bot.event
async def on_ready():
    logger.info(f'{bot.user} erfolgreich gestartet')
    try:
        synced = await bot.tree.sync()
        logger.info(f'{len(synced)} Slash Commands synchronisiert')
        check_invoices.start()  # Mahnung-System starten
    except Exception as e:
        logger.error(f'Fehler beim Synchronisieren der Commands: {e}')

# Log-Channel einrichten
@bot.tree.command(name="log_channel_setzen", description="Setzt den Channel für System-Logs")
@app_commands.describe(channel="Der Channel für Log-Nachrichten")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        error_embed = discord.Embed(
            title="Zugriff verweigert",
            description="Nur Administratoren können den Log-Channel festlegen.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    config["log_channel_id"] = channel.id
    save_config(config)

    success_embed = discord.Embed(
        title="Log-Channel konfiguriert",
        description=f"Alle System-Logs werden nun in {channel.mention} gesendet.",
        color=COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=success_embed, ephemeral=True)

    # Log
    log_embed = discord.Embed(
        title="⚙️ Konfiguration geändert",
        description=f"Log-Channel wurde auf {channel.mention} gesetzt.",
        color=COLOR_INFO,
        timestamp=datetime.now()
    )
    log_embed.add_field(name="Geändert von", value=interaction.user.mention)
    await send_to_log_channel(interaction.guild, log_embed)

    logger.info(f"Log-Channel auf {channel.id} gesetzt von User {interaction.user.id}")

# Firmenkonto setzen
@bot.tree.command(name="firmenkonto_setzen", description="Setzt das Firmenkonto für Economy-Zahlungen")
@app_commands.describe(user="Der User des Firmenkontos")
async def set_company_account(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        error_embed = discord.Embed(
            title="Zugriff verweigert",
            description="Nur Administratoren können das Firmenkonto festlegen.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    config["company_account_id"] = user.id
    save_config(config)

    success_embed = discord.Embed(
        title="Firmenkonto konfiguriert",
        description=f"Das Firmenkonto wurde auf {user.mention} gesetzt.",
        color=COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=success_embed, ephemeral=True)

    # Log
    log_embed = discord.Embed(
        title="⚙️ Konfiguration geändert",
        description=f"Firmenkonto wurde auf {user.mention} gesetzt.",
        color=COLOR_INFO,
        timestamp=datetime.now()
    )
    log_embed.add_field(name="Geändert von", value=interaction.user.mention)
    await send_to_log_channel(interaction.guild, log_embed)

# Auswahlmenü für Versicherungen
class InsuranceSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=insurance,
                description=f"Monatsbeitrag: {data['price']:,.2f} €",
                value=insurance
            )
            for insurance, data in INSURANCE_TYPES.items()
        ]
        super().__init__(
            placeholder="Wählen Sie die gewünschten Versicherungen aus...",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="insurance_select"
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = False

        total = sum(INSURANCE_TYPES[ins]["price"] for ins in self.values)
        preview_text = "\n".join(f"▸ {ins} — {INSURANCE_TYPES[ins]['price']:,.2f} €" for ins in self.values)

        preview_embed = discord.Embed(
            title="Versicherungen ausgewählt",
            description=f"**Ausgewählte Versicherungen:**\n{preview_text}\n\n**Gesamtbeitrag (monatlich):** {total:,.2f} €",
            color=COLOR_INFO
        )
        preview_embed.set_footer(text="Klicken Sie auf 'Kundenakte erstellen', um fortzufahren.")

        await interaction.response.edit_message(embed=preview_embed, view=view)

class InsuranceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.selected_insurances = []
        self.confirmed = False
        self.add_item(InsuranceSelect())

        confirm_button = discord.ui.Button(
            label="Kundenakte erstellen",
            style=discord.ButtonStyle.green,
            custom_id="confirm_insurance",
            disabled=True
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

    async def confirm_callback(self, interaction: discord.Interaction):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# Kundenakte erstellen
@bot.tree.command(name="kundenakte_erstellen", description="Erstellt eine neue Kundenakte im Archiv")
@app_commands.describe(
    forum_channel="Forum-Channel für Kundenakten",
    rp_name="RP-Name des Versicherungsnehmers",
    hbpay_nummer="HBpay Kontonummer",
    economy_id="Economy-ID des Versicherungsnehmers"
)
async def create_customer(
    interaction: discord.Interaction,
    forum_channel: discord.ForumChannel,
    rp_name: str,
    hbpay_nummer: str,
    economy_id: str
):
    view = InsuranceView()

    select_embed = discord.Embed(
        title="Versicherungen auswählen",
        description="Bitte wählen Sie die gewünschten Versicherungen für den Versicherungsnehmer aus dem Dropdown-Menü aus.\n\nNach der Auswahl klicken Sie auf den Button **'Kundenakte erstellen'**, um fortzufahren.",
        color=COLOR_INFO
    )

    await interaction.response.send_message(embed=select_embed, view=view, ephemeral=True)
    await view.wait()

    if not view.confirmed:
        timeout_embed = discord.Embed(
            title="Zeitüberschreitung",
            description="Die Auswahl wurde nicht rechtzeitig bestätigt. Bitte versuchen Sie es erneut.",
            color=COLOR_WARNING
        )
        await interaction.edit_original_response(embed=timeout_embed, view=None)
        return

    insurance_select = view.children[0]
    if not insurance_select.values:
        error_embed = discord.Embed(
            title="Keine Auswahl getroffen",
            description="Es wurden keine Versicherungen ausgewählt.",
            color=COLOR_ERROR
        )
        await interaction.edit_original_response(embed=error_embed, view=None)
        return

    insurance_list = insurance_select.values

    logger.info(f"Kundenakte wird erstellt von User {interaction.user.id} für {rp_name}")

    try:
        customer_id = generate_customer_id()
        total_price = sum(INSURANCE_TYPES[ins]["price"] for ins in insurance_list)

        embed = discord.Embed(
            title="Versicherungsakte",
            color=COLOR_PRIMARY,
            timestamp=datetime.now()
        )
        embed.add_field(name="Versicherungsnehmer-ID", value=f"`{customer_id}`", inline=True)
        embed.add_field(name="Versicherungsnehmer", value=rp_name, inline=True)
        embed.add_field(name="‎", value="‎", inline=True)
        embed.add_field(name="HBpay Kontonummer", value=f"`{hbpay_nummer}`", inline=True)
        embed.add_field(name="Economy-ID", value=f"`{economy_id}`", inline=True)
        embed.add_field(name="‎", value="‎", inline=True)

        insurance_text = "\n".join(
            f"▸ {ins} — `{INSURANCE_TYPES[ins]['price']:,.2f} €/Monat`" 
            for ins in insurance_list
        )
        embed.add_field(name="Abgeschlossene Versicherungen", value=insurance_text, inline=False)
        embed.add_field(name="Gesamtbeitrag (monatlich)", value=f"**{total_price:,.2f} €**", inline=False)

        embed.add_field(name="‎", value="─────────────────────────────", inline=False)
        embed.add_field(
            name="Aktenanlage",
            value=f"Bearbeitet von: {interaction.user.mention}\nDatum: {datetime.now().strftime('%d.%m.%Y, %H:%M')} Uhr",
            inline=False
        )

        thread = await forum_channel.create_thread(
            name=f"Akte {customer_id} | {rp_name}",
            content="**Versicherungsakte**",
            embed=embed
        )

        data['customers'][customer_id] = {
            "rp_name": rp_name,
            "hbpay_nummer": hbpay_nummer,
            "economy_id": economy_id,
            "versicherungen": insurance_list,
            "total_monthly_price": total_price,
            "thread_id": thread.thread.id,
            "discord_user_id": interaction.user.id,
            "created_at": datetime.now().isoformat(),
            "created_by": interaction.user.id
        }
        save_data(data)

        member = interaction.guild.get_member(interaction.user.id)
        assigned_roles = []
        for insurance in insurance_list:
            role_name = INSURANCE_TYPES[insurance]["role"]
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if not role:
                role = await interaction.guild.create_role(
                    name=role_name,
                    color=discord.Color.from_rgb(44, 62, 80)
                )
                logger.info(f"Rolle erstellt: {role_name}")
            await member.add_roles(role)
            assigned_roles.append(role_name)

        add_log_entry(
            "KUNDENAKTE_ERSTELLT",
            interaction.user.id,
            {
                "customer_id": customer_id,
                "rp_name": rp_name,
                "versicherungen": insurance_list,
                "total_price": total_price
            }
        )

        log_embed = discord.Embed(
            title="📋 Neue Kundenakte erstellt",
            color=COLOR_SUCCESS,
            timestamp=datetime.now()
        )
        log_embed.add_field(name="Versicherungsnehmer-ID", value=f"`{customer_id}`", inline=True)
        log_embed.add_field(name="Name", value=rp_name, inline=True)
        log_embed.add_field(name="Bearbeiter", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Versicherungen", value=str(len(insurance_list)), inline=True)
        log_embed.add_field(name="Monatsbeitrag", value=f"{total_price:,.2f} €", inline=True)
        await send_to_log_channel(interaction.guild, log_embed)

        success_embed = discord.Embed(
            title="Kundenakte erfolgreich angelegt",
            description="Die Versicherungsakte wurde erfolgreich im System hinterlegt.",
            color=COLOR_SUCCESS
        )
        success_embed.add_field(name="Versicherungsnehmer-ID", value=f"`{customer_id}`", inline=True)
        success_embed.add_field(name="Aktenarchiv", value=thread.thread.mention, inline=True)
        success_embed.add_field(name="Monatsbeitrag", value=f"{total_price:,.2f} €", inline=True)

        await interaction.edit_original_response(embed=success_embed, view=None)
        logger.info(f"Kundenakte {customer_id} erfolgreich erstellt")

    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Kundenakte: {e}", exc_info=True)
        error_embed = discord.Embed(
            title="Fehler bei der Aktenanlage",
            description=f"Es ist ein Fehler aufgetreten: {str(e)}",
            color=COLOR_ERROR
        )
        try:
            await interaction.edit_original_response(embed=error_embed, view=None)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

# Rechnung mit Zahlungsoptionen
class PaymentView(discord.ui.View):
    def __init__(self, invoice_id, customer_id):
        super().__init__(timeout=None)
        self.invoice_id = invoice_id
        self.customer_id = customer_id

    @discord.ui.button(label="Mit HBpay zahlen", style=discord.ButtonStyle.primary, custom_id="pay_hbpay", emoji="💳")
    async def pay_hbpay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_payment(interaction, "HBpay")

    @discord.ui.button(label="Mit Economy zahlen", style=discord.ButtonStyle.primary, custom_id="pay_economy", emoji="💰")
    async def pay_economy(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Firmenkonto pingen
        if config.get("company_account_id"):
            company_user = interaction.guild.get_member(config["company_account_id"])
            if company_user:
                await interaction.channel.send(f"{company_user.mention} - Economy-Zahlung für Rechnung `{self.invoice_id}` wurde eingereicht.")
        await self.process_payment(interaction, "Economy")

    @discord.ui.button(label="Zahlung bestätigen (Mitarbeiter)", style=discord.ButtonStyle.green, custom_id="confirm_payment", emoji="✅")
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prüfen ob Mitarbeiter oder Firmenkonto
        finance_role = discord.utils.get(interaction.guild.roles, name="「 Leitungsebene 」")
        is_company = config.get("company_account_id") == interaction.user.id

        if finance_role not in interaction.user.roles and not is_company:
            error_embed = discord.Embed(
                title="Zugriff verweigert",
                description="Nur Mitarbeiter der Leitungsebene oder das Firmenkonto können Zahlungen bestätigen.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        # Alle Buttons deaktivieren
        for item in self.children:
            item.disabled = True

        if self.invoice_id in data['invoices']:
            data['invoices'][self.invoice_id]['paid'] = True
            data['invoices'][self.invoice_id]['paid_by'] = interaction.user.id
            data['invoices'][self.invoice_id]['paid_at'] = datetime.now().isoformat()
            data['invoices'][self.invoice_id]['reminder_count'] = 0
            save_data(data)

            add_log_entry(
                "RECHNUNG_BEZAHLT",
                interaction.user.id,
                {
                    "invoice_id": self.invoice_id,
                    "customer_id": self.customer_id
                }
            )

            log_embed = discord.Embed(
                title="💰 Zahlungseingang bestätigt",
                color=COLOR_SUCCESS,
                timestamp=datetime.now()
            )
            log_embed.add_field(name="Rechnungsnummer", value=f"`{self.invoice_id}`", inline=True)
            log_embed.add_field(name="Bestätigt von", value=interaction.user.mention, inline=True)
            await send_to_log_channel(interaction.guild, log_embed)

        await interaction.response.edit_message(view=self)
        success_embed = discord.Embed(
            title="✅ Zahlung bestätigt",
            description=f"Die Rechnung `{self.invoice_id}` wurde als bezahlt markiert.",
            color=COLOR_SUCCESS
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

    async def process_payment(self, interaction: discord.Interaction, method: str):
        info_embed = discord.Embed(
            title=f"Zahlungsmethode ausgewählt: {method}",
            description=f"Bitte führen Sie die Zahlung über {method} durch.\n\nEin Mitarbeiter wird die Zahlung anschließend bestätigen.",
            color=COLOR_INFO
        )
        await interaction.response.send_message(embed=info_embed, ephemeral=True)

@bot.tree.command(name="rechnung_ausstellen", description="Erstellt eine Versicherungsrechnung")
@app_commands.describe(
    customer_id="Versicherungsnehmer-ID",
    channel="Channel für die Rechnungsstellung"
)
async def create_invoice(
    interaction: discord.Interaction,
    customer_id: str,
    channel: discord.TextChannel
):
    await interaction.response.defer(ephemeral=True)
    logger.info(f"Rechnung wird erstellt von User {interaction.user.id} für Kunde {customer_id}")

    try:
        if customer_id not in data['customers']:
            error_embed = discord.Embed(
                title="Kunde nicht gefunden",
                description=f"Es existiert keine Akte mit der Versicherungsnehmer-ID `{customer_id}`.",
                color=COLOR_ERROR
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        customer = data['customers'][customer_id]
        invoice_id = generate_invoice_id()
        betrag = customer['total_monthly_price']

        # Zahlungsfrist: 3 Tage
        due_date = datetime.now() + timedelta(days=3)

        embed = discord.Embed(
            title="Versicherungsrechnung",
            color=COLOR_PRIMARY,
            timestamp=datetime.now()
        )
        embed.add_field(name="Rechnungsnummer", value=f"`{invoice_id}`", inline=True)
        embed.add_field(name="Rechnungsdatum", value=datetime.now().strftime('%d.%m.%Y'), inline=True)
        embed.add_field(name="Fälligkeitsdatum", value=due_date.strftime('%d.%m.%Y'), inline=True)

        embed.add_field(name="‎", value="**Versicherungsnehmer**", inline=False)
        embed.add_field(name="Name", value=customer['rp_name'], inline=True)
        embed.add_field(name="Kunden-ID", value=f"`{customer_id}`", inline=True)
        embed.add_field(name="‎", value="‎", inline=True)

        embed.add_field(name="‎", value="**Zahlungsinformationen**", inline=False)
        embed.add_field(name="HBpay Nummer", value=f"`{customer['hbpay_nummer']}`", inline=True)
        embed.add_field(name="Economy-ID", value=f"`{customer['economy_id']}`", inline=True)
        embed.add_field(name="‎", value="‎", inline=True)

        insurance_details = "\n".join(
            f"▸ {ins}\n   `{INSURANCE_TYPES[ins]['price']:,.2f} €`" 
            for ins in customer['versicherungen']
        )
        embed.add_field(name="Versicherte Positionen", value=insurance_details, inline=False)

        embed.add_field(name="‎", value="─────────────────────────────", inline=False)
        embed.add_field(name="Zwischensumme", value=f"{betrag:,.2f} €", inline=True)
        embed.add_field(name="MwSt. (0%)", value="0,00 €", inline=True)
        embed.add_field(name="**Rechnungsbetrag**", value=f"**{betrag:,.2f} €**", inline=True)

        embed.add_field(name="‎", value="─────────────────────────────", inline=False)
        embed.add_field(name="Status", value="⏳ Zahlung ausstehend", inline=False)
        embed.set_footer(text=f"Ausgestellt von {interaction.user.display_name} • Bitte wählen Sie eine Zahlungsmethode")

        view = PaymentView(invoice_id, customer_id)
        message = await channel.send(embed=embed, view=view)

        data['invoices'][invoice_id] = {
            "customer_id": customer_id,
            "betrag": betrag,
            "original_betrag": betrag,
            "paid": False,
            "message_id": message.id,
            "channel_id": channel.id,
            "due_date": due_date.isoformat(),
            "reminder_count": 0,
            "created_at": datetime.now().isoformat(),
            "created_by": interaction.user.id
        }
        save_data(data)

        add_log_entry(
            "RECHNUNG_ERSTELLT",
            interaction.user.id,
            {
                "invoice_id": invoice_id,
                "customer_id": customer_id,
                "betrag": betrag,
                "due_date": due_date.strftime('%d.%m.%Y')
            }
        )

        log_embed = discord.Embed(
            title="🧾 Neue Rechnung ausgestellt",
            color=COLOR_INFO,
            timestamp=datetime.now()
        )
        log_embed.add_field(name="Rechnungsnummer", value=f"`{invoice_id}`", inline=True)
        log_embed.add_field(name="Kunde", value=customer['rp_name'], inline=True)
        log_embed.add_field(name="Betrag", value=f"{betrag:,.2f} €", inline=True)
        log_embed.add_field(name="Fällig am", value=due_date.strftime('%d.%m.%Y'), inline=True)
        log_embed.add_field(name="Ausgestellt von", value=interaction.user.mention, inline=True)
        await send_to_log_channel(interaction.guild, log_embed)

        success_embed = discord.Embed(
            title="Rechnung erfolgreich ausgestellt",
            description="Die Rechnung wurde erstellt und versendet.",
            color=COLOR_SUCCESS
        )
        success_embed.add_field(name="Rechnungsnummer", value=f"`{invoice_id}`", inline=True)
        success_embed.add_field(name="Betrag", value=f"{betrag:,.2f} €", inline=True)
        success_embed.add_field(name="Fällig am", value=due_date.strftime('%d.%m.%Y'), inline=True)

        await interaction.followup.send(embed=success_embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Fehler beim Erstellen der Rechnung: {e}", exc_info=True)
        error_embed = discord.Embed(
            title="Fehler bei der Rechnungsstellung",
            description=f"Es ist ein Fehler aufgetreten: {str(e)}",
            color=COLOR_ERROR
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

# Mahnungs-System
@tasks.loop(hours=24)
async def check_invoices():
    """Überprüft täglich alle Rechnungen und sendet Mahnungen"""
    try:
        now = datetime.now()
        for invoice_id, invoice_data in list(data['invoices'].items()):
            if invoice_data.get('paid', False):
                continue

            due_date = datetime.fromisoformat(invoice_data['due_date'])
            days_overdue = (now - due_date).days

            if days_overdue < 0:
                continue

            reminder_count = invoice_data.get('reminder_count', 0)

            # Erste Mahnung (Tag 0 nach Fälligkeit)
            if days_overdue == 0 and reminder_count == 0:
                await send_reminder(invoice_id, invoice_data, 1, 0)
                data['invoices'][invoice_id]['reminder_count'] = 1
                save_data(data)

            # Zweite Mahnung (Tag 1, +5%)
            elif days_overdue == 1 and reminder_count == 1:
                new_amount = invoice_data['original_betrag'] * 1.05
                data['invoices'][invoice_id]['betrag'] = new_amount
                await send_reminder(invoice_id, invoice_data, 2, 5)
                data['invoices'][invoice_id]['reminder_count'] = 2
                save_data(data)

            # Dritte Mahnung (Tag 2, +10% vom Original)
            elif days_overdue == 2 and reminder_count == 2:
                new_amount = invoice_data['original_betrag'] * 1.10
                data['invoices'][invoice_id]['betrag'] = new_amount
                await send_reminder(invoice_id, invoice_data, 3, 10)
                data['invoices'][invoice_id]['reminder_count'] = 3
                save_data(data)

    except Exception as e:
        logger.error(f"Fehler bei Mahnungsprüfung: {e}", exc_info=True)

async def send_reminder(invoice_id, invoice_data, reminder_number, surcharge_percent):
    """Sendet eine Mahnung"""
    try:
        for guild in bot.guilds:
            channel = guild.get_channel(invoice_data['channel_id'])
            if not channel:
                continue

            customer = data['customers'].get(invoice_data['customer_id'])
            if not customer:
                continue

            customer_user = guild.get_member(customer['discord_user_id'])

            surcharge_text = f" (+{surcharge_percent}% Mahngebühr)" if surcharge_percent > 0 else ""

            embed = discord.Embed(
                title=f"⚠️ {reminder_number}. Mahnung",
                description=f"Die Rechnung `{invoice_id}` ist überfällig.",
                color=COLOR_WARNING if reminder_number < 3 else COLOR_ERROR,
                timestamp=datetime.now()
            )
            embed.add_field(name="Rechnungsnummer", value=f"`{invoice_id}`", inline=True)
            embed.add_field(name="Kunde", value=customer['rp_name'], inline=True)
            embed.add_field(name="Mahnung", value=f"{reminder_number}. Mahnung", inline=True)
            embed.add_field(name="Ursprünglicher Betrag", value=f"{invoice_data['original_betrag']:,.2f} €", inline=True)
            embed.add_field(name="Aktueller Betrag", value=f"**{invoice_data['betrag']:,.2f} €{surcharge_text}**", inline=True)

            if customer_user:
                await channel.send(f"{customer_user.mention}", embed=embed)
            else:
                await channel.send(embed=embed)

            # Log
            log_embed = discord.Embed(
                title=f"📨 {reminder_number}. Mahnung versendet",
                color=COLOR_WARNING,
                timestamp=datetime.now()
            )
            log_embed.add_field(name="Rechnungsnummer", value=f"`{invoice_id}`", inline=True)
            log_embed.add_field(name="Kunde", value=customer['rp_name'], inline=True)
            log_embed.add_field(name="Neuer Betrag", value=f"{invoice_data['betrag']:,.2f} €", inline=True)
            await send_to_log_channel(guild, log_embed)

            add_log_entry(
                f"MAHNUNG_{reminder_number}",
                0,
                {
                    "invoice_id": invoice_id,
                    "customer_id": invoice_data['customer_id'],
                    "surcharge": surcharge_percent
                }
            )

            break

    except Exception as e:
        logger.error(f"Fehler beim Senden der Mahnung: {e}", exc_info=True)

# Ticket-System
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kundenkontakt anfragen", style=discord.ButtonStyle.primary, custom_id="open_ticket", emoji="📞")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"Ticket-Button geklickt von User {interaction.user.id}")
        await interaction.response.send_modal(TicketModal())

class TicketModal(discord.ui.Modal, title="Kundenkontakt-Anfrage"):
    customer_id_input = discord.ui.TextInput(
        label="Versicherungsnehmer-ID",
        placeholder="VN-24123456",
        required=True,
        max_length=20
    )

    reason = discord.ui.TextInput(
        label="Grund der Kontaktaufnahme",
        style=discord.TextStyle.paragraph,
        placeholder="Bitte beschreiben Sie detailliert den Anlass für die Kontaktaufnahme...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Ticket wird erstellt von User {interaction.user.id}")

        try:
            customer_id = self.customer_id_input.value

            if customer_id not in data['customers']:
                error_embed = discord.Embed(
                    title="Kunde nicht gefunden",
                    description=f"Es existiert keine Akte mit der Versicherungsnehmer-ID `{customer_id}`.",
                    color=COLOR_ERROR
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            customer = data['customers'][customer_id]
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="Support-Tickets")

            if not category:
                category = await guild.create_category("Support-Tickets")

            ticket_channel = await category.create_text_channel(
                name=f"ticket-{customer_id.lower()}",
                topic=f"Kundenkontakt: {customer['rp_name']} | {customer_id}"
            )

            customer_user = guild.get_member(customer['discord_user_id'])

            # Verbessertes Ticket-Embed
            embed = discord.Embed(
                title="🎫 Support-Ticket",
                description="**Ein neues Kundenkontakt-Ticket wurde eröffnet**\n\nWillkommen! Dieses Ticket wurde erstellt, um eine professionelle Kommunikation zwischen Mitarbeiter und Versicherungsnehmer zu ermöglichen.",
                color=COLOR_INFO,
                timestamp=datetime.now()
            )

            embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━", value="**Ticket-Informationen**", inline=False)
            embed.add_field(name="📊 Status", value="🟢 Offen", inline=True)
            embed.add_field(name="⏰ Erstellt am", value=datetime.now().strftime('%d.%m.%Y, %H:%M'), inline=True)
            embed.add_field(name="🔢 Priorität", value="Normal", inline=True)

            embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━", value="**Beteiligte Personen**", inline=False)
            embed.add_field(name="👤 Mitarbeiter", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=True)
            embed.add_field(name="👥 Versicherungsnehmer", value=f"{customer['rp_name']}\n`{customer_id}`", inline=True)
            embed.add_field(name="‎", value="‎", inline=True)

            embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━", value="**Anlass der Kontaktaufnahme**", inline=False)
            embed.add_field(name="📝 Beschreibung", value=self.reason.value, inline=False)

            embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━", value="**Kundeninformationen**", inline=False)
            insurance_info = "\n".join(f"▸ {ins}" for ins in customer['versicherungen'])
            embed.add_field(name="🛡️ Versicherungen", value=insurance_info, inline=False)
            embed.add_field(name="💰 Monatsbeitrag", value=f"`{customer['total_monthly_price']:,.2f} €`", inline=True)
            embed.add_field(name="💳 HBpay", value=f"`{customer['hbpay_nummer']}`", inline=True)
            embed.add_field(name="🆔 Economy-ID", value=f"`{customer['economy_id']}`", inline=True)

            embed.set_footer(text="Support-System • Nutzen Sie den Button unten, um dieses Ticket zu schließen")

            # Close-Button hinzufügen
            close_view = TicketCloseView(ticket_channel.id, customer_id)

            mentions = [interaction.user.mention]
            if customer_user:
                mentions.append(customer_user.mention)

            await ticket_channel.send(" ".join(mentions), embed=embed, view=close_view)

            add_log_entry(
                "TICKET_ERSTELLT",
                interaction.user.id,
                {
                    "customer_id": customer_id,
                    "channel_id": ticket_channel.id,
                    "reason": self.reason.value
                }
            )

            log_embed = discord.Embed(
                title="🎫 Neues Support-Ticket",
                color=COLOR_INFO,
                timestamp=datetime.now()
            )
            log_embed.add_field(name="Ticket-Channel", value=ticket_channel.mention, inline=True)
            log_embed.add_field(name="Kunde", value=customer['rp_name'], inline=True)
            log_embed.add_field(name="Erstellt von", value=interaction.user.mention, inline=True)
            await send_to_log_channel(interaction.guild, log_embed)

            success_embed = discord.Embed(
                title="Ticket erfolgreich erstellt",
                description="Die Kundenkontakt-Anfrage wurde erstellt.",
                color=COLOR_SUCCESS
            )
            success_embed.add_field(name="Ticket-Channel", value=ticket_channel.mention, inline=True)

            await interaction.followup.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Tickets: {e}", exc_info=True)
            error_embed = discord.Embed(
                title="Fehler bei der Ticket-Erstellung",
                description=f"Es ist ein Fehler aufgetreten: {str(e)}",
                color=COLOR_ERROR
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self, channel_id, customer_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.customer_id = customer_id

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Nur Mitarbeiter können Tickets schließen
        finance_role = discord.utils.get(interaction.guild.roles, name="「 Leitungsebene 」")
        if finance_role not in interaction.user.roles:
            error_embed = discord.Embed(
                title="Zugriff verweigert",
                description="Nur Mitarbeiter können Tickets schließen.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        channel = interaction.channel

        close_embed = discord.Embed(
            title="🔒 Ticket wird geschlossen",
            description=f"Dieses Ticket wird in 5 Sekunden geschlossen und archiviert.\n\nGeschlossen von: {interaction.user.mention}",
            color=COLOR_WARNING,
            timestamp=datetime.now()
        )

        await interaction.response.send_message(embed=close_embed)

        # Log
        log_embed = discord.Embed(
            title="🔒 Ticket geschlossen",
            color=COLOR_WARNING,
            timestamp=datetime.now()
        )
        log_embed.add_field(name="Ticket-Channel", value=channel.mention, inline=True)
        log_embed.add_field(name="Kunde", value=f"`{self.customer_id}`", inline=True)
        log_embed.add_field(name="Geschlossen von", value=interaction.user.mention, inline=True)
        await send_to_log_channel(interaction.guild, log_embed)

        add_log_entry(
            "TICKET_GESCHLOSSEN",
            interaction.user.id,
            {
                "customer_id": self.customer_id,
                "channel_id": self.channel_id
            }
        )

        import asyncio
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket geschlossen von {interaction.user}")

@bot.tree.command(name="ticket_setup", description="Richtet das Ticket-System ein")
@app_commands.describe(channel="Channel für das Ticket-Panel")
async def setup_tickets(interaction: discord.Interaction, channel: discord.TextChannel):
    logger.info(f"Ticket-System wird eingerichtet von User {interaction.user.id} in Channel {channel.id}")

    try:
        embed = discord.Embed(
            title="🎫 Kundenkontakt-System",
            description="**Willkommen beim professionellen Kundenkontakt-System**\n\nNutzen Sie diese Funktion, um eine direkte und strukturierte Kontaktaufnahme mit einem Versicherungsnehmer zu initiieren.\n\n**Hinweise:**\n▸ Stellen Sie sicher, dass die Versicherungsnehmer-ID korrekt ist\n▸ Beschreiben Sie den Kontaktgrund präzise und ausführlich\n▸ Das Ticket wird automatisch dem entsprechenden Kunden zugeordnet",
            color=COLOR_PRIMARY
        )
        embed.set_footer(text="Versicherungs-Management-System v2.0")

        view = TicketView()
        await channel.send(embed=embed, view=view)

        success_embed = discord.Embed(
            title="Ticket-System aktiviert",
            description=f"Das Kundenkontakt-System wurde erfolgreich in {channel.mention} eingerichtet.",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

        add_log_entry(
            "TICKET_SYSTEM_SETUP",
            interaction.user.id,
            {"channel_id": channel.id}
        )

        log_embed = discord.Embed(
            title="⚙️ Ticket-System eingerichtet",
            color=COLOR_INFO,
            timestamp=datetime.now()
        )
        log_embed.add_field(name="Channel", value=channel.mention, inline=True)
        log_embed.add_field(name="Eingerichtet von", value=interaction.user.mention, inline=True)
        await send_to_log_channel(interaction.guild, log_embed)

    except Exception as e:
        logger.error(f"Fehler beim Einrichten des Ticket-Systems: {e}", exc_info=True)
        error_embed = discord.Embed(
            title="Fehler beim Setup",
            description=f"Es ist ein Fehler aufgetreten: {str(e)}",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# Log anzeigen
@bot.tree.command(name="logs_anzeigen", description="Zeigt die letzten Bot-Aktivitäten an")
@app_commands.describe(anzahl="Anzahl der anzuzeigenden Log-Einträge (Standard: 10)")
async def show_logs(interaction: discord.Interaction, anzahl: int = 10):
    logger.info(f"Logs werden abgerufen von User {interaction.user.id}")

    if not interaction.user.guild_permissions.administrator:
        error_embed = discord.Embed(
            title="Zugriff verweigert",
            description="Nur Administratoren können die System-Logs einsehen.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        if not data['logs']:
            info_embed = discord.Embed(
                title="Keine Logs vorhanden",
                description="Es sind noch keine Aktivitäten protokolliert worden.",
                color=COLOR_INFO
            )
            await interaction.followup.send(embed=info_embed, ephemeral=True)
            return

        recent_logs = data['logs'][-anzahl:]
        recent_logs.reverse()

        embed = discord.Embed(
            title="System-Aktivitätsprotokoll",
            description=f"Die letzten {len(recent_logs)} Aktivitäten im System",
            color=COLOR_PRIMARY,
            timestamp=datetime.now()
        )

        for log in recent_logs:
            timestamp = datetime.fromisoformat(log['timestamp']).strftime('%d.%m.%Y %H:%M')
            user = interaction.guild.get_member(log['user_id']) if log['user_id'] != 0 else None
            user_name = user.display_name if user else "System"

            action_names = {
                "KUNDENAKTE_ERSTELLT": "Kundenakte erstellt",
                "RECHNUNG_ERSTELLT": "Rechnung ausgestellt",
                "RECHNUNG_BEZAHLT": "Rechnung bezahlt",
                "MAHNUNG_1": "1. Mahnung versendet",
                "MAHNUNG_2": "2. Mahnung versendet (+5%)",
                "MAHNUNG_3": "3. Mahnung versendet (+10%)",
                "TICKET_ERSTELLT": "Ticket erstellt",
                "TICKET_GESCHLOSSEN": "Ticket geschlossen",
                "TICKET_SYSTEM_SETUP": "Ticket-System eingerichtet"
            }

            action_display = action_names.get(log['action'], log['action'])
            details_text = ", ".join([f"{k}: {v}" for k, v in log['details'].items() if k != 'reason'])

            embed.add_field(
                name=f"{action_display}",
                value=f"**Zeit:** {timestamp}\n**Bearbeiter:** {user_name}\n**Details:** {details_text}",
                inline=False
            )

        embed.set_footer(text="Versicherungs-Management-System")
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Fehler beim Anzeigen der Logs: {e}", exc_info=True)
        error_embed = discord.Embed(
            title="Fehler beim Laden der Logs",
            description=f"Es ist ein Fehler aufgetreten: {str(e)}",
            color=COLOR_ERROR
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

# Für Render: Keep-Alive mit Flask
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Insurance Bot läuft erfolgreich!"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": bot.user.name if bot.user else "starting"}

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot starten
if __name__ == "__main__":
    keep_alive()  # Webserver für Render

    # Token aus Umgebungsvariable
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN nicht gefunden! Bitte in Render-Umgebungsvariablen setzen.")
    else:
        logger.info("Bot wird gestartet...")
        bot.run(token)