from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from app.keyboards.lesson import lesson_kb
from app.keyboards.quiz import quiz_kb
from app.locales import t
from app.states.lesson import LessonStates
from app.services.memory import LESSONS
from app.services.stats import update_user_activity

router = Router()


@router.callback_query(F.data == "lesson:start_questions")
async def start_questions(call: CallbackQuery, state: FSMContext, lang: str):
    # Стрик здесь НЕ засчитываем — только открытие вопросов.
    # День засчитается когда пользователь реально ответит (в check_answer).
    lesson = LESSONS.get(call.from_user.id)

    if not lesson:
        await call.answer(t("lesson_not_found", lang))
        return

    questions = lesson.get("questions", [])

    if not questions:
        await call.message.answer(t("questions_not_found", lang))
        await call.answer()
        return

    await state.update_data(
        questions=questions,
        question_index=0,
        score=0
    )

    await state.set_state(LessonStates.answering_question)

    q = questions[0]
    question_label = t("question", lang)

    text = (
        f"{question_label} 1/{len(questions)}\n\n"
        f"{q['question']}\n\n"
        f"1. {q['options'][0]}\n"
        f"2. {q['options'][1]}\n"
        f"3. {q['options'][2]}"
    )

    await call.message.answer(text, reply_markup=quiz_kb())
    await call.answer()


@router.callback_query(F.data == "lesson:show_translation")
async def show_translation(call: CallbackQuery, lang: str):
    lesson = LESSONS.get(call.from_user.id)

    if not lesson:
        await call.answer(t("lesson_not_found", lang))
        return

    translation = lesson.get("translation")
    if not translation:
        await call.answer(t("translation_not_found", lang))
        return

    await call.message.edit_text(
        f"{lesson['title']}\n\n"
        f"{lesson['text']}\n\n"
        f"{t('translation_label', lang)}\n\n"
        f"{lesson['translation']}",
        reply_markup=lesson_kb(lang, show_translation=False)
    )
    await call.answer()


@router.callback_query(F.data.startswith("quiz:answer:"))
async def check_answer(call: CallbackQuery, state: FSMContext, lang: str):
    # Реальное учебное действие — засчитываем день (один раз, тут).
    await update_user_activity(call.from_user.id)

    choice = int(call.data.split(":")[2]) - 1
    data = await state.get_data()

    questions = data["questions"]
    index = data["question_index"]
    score = data["score"]

    q = questions[index]
    user_answer = q["options"][choice]
    correct_answer = q["answer"]

    if user_answer == correct_answer:
        score += 1
        await call.message.answer(t("correct", lang))
    else:
        await call.message.answer(
            f"{t('incorrect', lang)}\n\n"
            f"{t('correct_answer', lang)}\n{correct_answer}"
        )

    index += 1

    if index >= len(questions):
        await call.message.answer(
            f"{t('lesson_finished', lang)}\n\n"
            f"{t('answers_count', lang).format(score=score, total=len(questions))}"
        )
        await state.clear()
        await call.answer()
        return

    await state.update_data(question_index=index, score=score)

    q = questions[index]
    question_label = t("question", lang)

    text = (
        f"{question_label} {index + 1}/{len(questions)}\n\n"
        f"{q['question']}\n\n"
        f"1. {q['options'][0]}\n"
        f"2. {q['options'][1]}\n"
        f"3. {q['options'][2]}"
    )

    await call.message.answer(text, reply_markup=quiz_kb())
    await call.answer()