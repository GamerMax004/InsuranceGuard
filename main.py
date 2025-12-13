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

# Für Replit: Keep-Alive mit Flask
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot läuft!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot starten
if __name__ == "__main__":
    keep_alive()  # Für Replit
    bot.run(os.getenv('DISCORD_TOKEN'))  # Token aus Umgebungsvariable
bot.run('MTQyNDc2OTE4NDk5MDEwNTc0MQ.G_f0ic.LDkv6dtig5US9vJxq_gbAxTmYj70i-vP4Q9OYA')