import asyncio
import datetime
import functools
import random

from src.bases.engines.data_models import EngineOperatorQuiz
from src.bases.engines.event_participators import QuizEventParticipator
from src.constants.engine import EVENT_PARTICIPATION_STARTED_STATUS, EVENT_PARTICIPATION_ENDED_STATUS
from src.constants.engine import events as event_constants
from src.utils import get_now, capture_error

STARTING_TITLE: str = 'QUIZ EVENT'
ENDING_TITLE: str = 'QUIZ EVENT FINISHED'
LOGGING_MSG_PREFIX: str = '[QUIZ]'

QUESTION_TITLES: list[str] = [
    'PORTUGUESE - DISCOVER THE WORD:',
    'ENGLISH - DISCOVER THE WORD:',
    'SPANISH - DISCOVER THE WORD:',
    'FIND THE VALUE OF X:',
    'SOLVE:',
]


class UnityMegaMUQuizEventParticipator(QuizEventParticipator):
    async def _wait_for_started(self):
        self._logger.info(f'{LOGGING_MSG_PREFIX} Waiting for event to start')

        target_titles = set(
            [
                STARTING_TITLE
            ] + QUESTION_TITLES
        )

        if self.participation.status == EVENT_PARTICIPATION_STARTED_STATUS:
            return

        while self.participation.status != EVENT_PARTICIPATION_STARTED_STATUS:
            for noti_title in self._get_notifications():
                if noti_title in target_titles:
                    self.participation.status = EVENT_PARTICIPATION_STARTED_STATUS
                    break
            await asyncio.sleep(1)

        self._logger.info(f'{LOGGING_MSG_PREFIX} Event started')

    def _is_event_ended(self) -> bool:
        if self.participation.status == EVENT_PARTICIPATION_ENDED_STATUS:
            return True
        if ENDING_TITLE in self._get_notifications():
            self.participation.status = EVENT_PARTICIPATION_ENDED_STATUS
            return True
        return False

    async def _wait_for_quiz(self) -> EngineOperatorQuiz | None:
        quiz_content = None
        quiz_title = None

        now = get_now()

        while not quiz_title:
            if self._is_event_ended():
                return None
            notifications = self._get_notifications(now)
            for noti in notifications:
                if noti not in QUESTION_TITLES:
                    continue

                quiz_title = noti
                break

            await asyncio.sleep(0.1)

        while not quiz_content:
            if self._is_event_ended():
                return None
            notifications = self._get_notifications(now)
            for index, noti_title in enumerate(notifications):
                if noti_title == quiz_title:
                    if index == 0:
                        break
                    quiz_content = notifications[index - 1]
                    break
            await asyncio.sleep(0.1)

        if 'DISCOVER THE WORD' in quiz_title:
            if '_' in quiz_content:
                quiz_type = event_constants.QUIZ_EVENT_COMPLETE_WORD_TYPE
            else:
                quiz_type = event_constants.QUIZ_EVENT_UNJUMBLE_WORD_TYPE
        else:
            quiz_type = event_constants.QUIZ_EVENT_SOLVE_MATH_TYPE

        return EngineOperatorQuiz(
            title=quiz_title,
            type=quiz_type,
            content=self._handle_quiz_content(
                quiz_type=quiz_type,
                content=quiz_content
            ),
        )

    def _is_quiz_solved(self, from_time: datetime.datetime) -> bool:
        if self._is_event_ended():
            return True

        for noti in self._get_notifications(from_time):
            if 'GOT IT RIGHT!' in noti:
                self._logger.info(f'{LOGGING_MSG_PREFIX} Quiz solved')
                return True
        return False

    @staticmethod
    def _handle_quiz_content(quiz_type: str,  content: str) -> str:
        if quiz_type == event_constants.QUIZ_EVENT_SOLVE_MATH_TYPE:
            return content.strip().lower()

        result_as_list = []
        for word in content.strip().lower().split('  '):
            result_as_list.append(word.strip().replace(' ', ''))

        return ' '.join(result_as_list)

    async def _solve_quiz(self, quiz: EngineOperatorQuiz):
        last_noti_check = get_now()
        attempted_results: set[str] = set()

        if quiz.type == event_constants.QUIZ_EVENT_SOLVE_MATH_TYPE:
            results = await self.engine.event_loop.run_in_executor(
                None,
                functools.partial(
                    self._solve_math,
                    input_data=quiz.content
                )
            )
            while not self._is_quiz_solved(last_noti_check):
                for r in results:

                    r = int(r)
                    if r in attempted_results:
                        continue

                    delay = random.uniform(
                        self.participation.setting.quiz_answer_min_delay,
                        self.participation.setting.quiz_answer_max_delay,
                    )
                    await asyncio.sleep(delay)
                    if self._is_quiz_solved(last_noti_check):
                        return
                    await self.engine.function_triggerer.send_chat(
                        f'/r {r}'
                    )
                    attempted_results.add(r)

                results = []
                await asyncio.sleep(1)
        else:
            language = quiz.title.split('-')[0]
            language = language.strip().lower().replace(' ', '')

            if quiz.type == event_constants.QUIZ_EVENT_COMPLETE_WORD_TYPE:
                def _check_for_content_updates() -> str | None:
                    _result = None
                    for _noti in self._get_notifications(last_noti_check):
                        if '_' in _noti:
                            _result = self._handle_quiz_content(
                                quiz_type=quiz.type,
                                content=_noti
                            )
                    return _result

                while not self._is_quiz_solved(last_noti_check):
                    last_noti_check = get_now()

                    highest_missing_ratio = 0
                    for word in quiz.content.split(' '):
                        missing_ratio = word.count('_') / len(word)
                        if missing_ratio > highest_missing_ratio:
                            highest_missing_ratio = missing_ratio

                    missing_ratio_threshold = self.participation.setting.quiz_missing_word_ratio_threshold
                    if highest_missing_ratio > missing_ratio_threshold:
                        await asyncio.sleep(2)
                        new_content = _check_for_content_updates()
                        if new_content and new_content != quiz.content:
                            quiz.content = new_content
                        continue

                    results = await self.engine.event_loop.run_in_executor(
                        None,
                        functools.partial(
                            self._complete_words,
                            language=language,
                            pattern=quiz.content
                        )
                    )

                    for r in results:
                        if r in attempted_results:
                            continue

                        delay = random.uniform(
                            self.participation.setting.quiz_answer_min_delay,
                            self.participation.setting.quiz_answer_max_delay,
                        )
                        await asyncio.sleep(delay)
                        if self._is_quiz_solved(last_noti_check):
                            return

                        await self.engine.function_triggerer.send_chat(
                            f'/r {r}'
                        )
                        attempted_results.add(r)

                        new_content = _check_for_content_updates()
                        if new_content and new_content != quiz.content:
                            quiz.content = new_content
                            break

                    await asyncio.sleep(1)
            else:
                results = await self.engine.event_loop.run_in_executor(
                    None,
                    functools.partial(
                        self._solve_jumbled_words,
                        language=language,
                        input_data=quiz.content
                    )
                )
                if not results:
                    self._logger.info(f'{LOGGING_MSG_PREFIX} Failed to find any results for quiz: {quiz.title} - {quiz.content}')
                    return

                while not self._is_quiz_solved(last_noti_check):
                    for r in results:
                        if r in attempted_results:
                            continue
                        delay = random.uniform(
                            self.participation.setting.quiz_answer_min_delay,
                            self.participation.setting.quiz_answer_max_delay,
                        )
                        await asyncio.sleep(delay)
                        if self._is_quiz_solved(last_noti_check):
                            return
                        await self.engine.function_triggerer.send_chat(
                            f'/r {r}'
                        )
                        attempted_results.add(r)

                    results = []
                    await asyncio.sleep(1)

    async def run(self):
        await self._wait_for_started()
        while not self._is_event_ended():
            quiz = await self._wait_for_quiz()
            if not quiz:
                await asyncio.sleep(0.1)
                continue
            try:
                await self._solve_quiz(quiz)
            except Exception as e:
                self._logger.info(f'{LOGGING_MSG_PREFIX} Failed to solve quiz {quiz.model_dump()}')
                capture_error(e)
            await asyncio.sleep(0.1)




