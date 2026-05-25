     ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .build()
    )

    app.add_handler(CommandHandler(["start", "help"], send_welcome_message))
    
    # حساسیت فقط به + درون متن یا ارسال فقط حرف p
    app.add_handler(MessageHandler(filters.Regex(re.compile(r'\+|(?i)^p$')), price_command_handler))

    log.info("Bot is now running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
